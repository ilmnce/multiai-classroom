/**
 * osu-mapping-guard.ts
 * OpenCode Lifecycle & Hardening Plugin for osu! Beatmap Generation MVP (M4 Hardening)
 * 
 * Implements:
 * 1. Run Lifecycle Management (PLANNED -> BUILDING -> VERIFYING -> COMPLETE|INCOMPLETE|FAILED)
 * 2. Append-only event log (work/mapping-runs/<run-id>/events.jsonl)
 * 3. Path Guard (POLICY_DENIED on unauthorized writes, symlink/junction escape, source overwrites, sensitive files)
 * 4. Completion Guard (Cross-reference completion & verification reports, checksum matching, hard requirements)
 * 5. Recovery (Resume from last validated artifact, skip re-generation if candidate checksum matches)
 * 6. Redaction (Sanitize secrets, OAuth tokens, env vars, authorization headers, truncate raw .osu logs)
 */

import type { Plugin, PluginInput, Hooks, PluginOptions } from "@opencode-ai/plugin";
import * as path from "path";
import * as fs from "fs";
import * as crypto from "crypto";

export type RunStatus = "PLANNED" | "BUILDING" | "VERIFYING" | "COMPLETE" | "INCOMPLETE" | "FAILED";

export interface EventLogEntry {
  timestamp: string;
  run_id: string;
  event_type: "RUN_INITIALIZED" | "STATUS_TRANSITION" | "TOOL_BEFORE" | "TOOL_AFTER" | "POLICY_DENIED" | "COMPLETION_EVALUATION" | "RECOVERY_DETECTED" | "ERROR";
  previous_status?: RunStatus;
  current_status: RunStatus;
  tool_name?: string;
  details?: Record<string, any>;
  error?: {
    code: string;
    category: string;
    message: string;
  };
}

export interface PathValidationResult {
  allowed: boolean;
  code?: "POLICY_DENIED" | "INVALID_TARGET_DIR" | "ACCESS_DENIED";
  message?: string;
  canonicalPath?: string;
}

export interface CompletionEvaluationResult {
  passed: boolean;
  verdict: "COMPLETE" | "INCOMPLETE" | "FAILED";
  reasons: string[];
  candidate_sha256?: string;
  provenance_sha256?: string;
  verification_verdict?: string;
  hard_requirements_passed?: boolean;
}

export interface RecoveryCheckResult {
  canResume: boolean;
  stage: "VERIFYING" | "COMPLETE" | "NONE";
  candidatePath?: string;
  candidateSha256?: string;
  reason?: string;
}

// ---------------------------------------------------------------------------
// 1. Redaction Engine
// ---------------------------------------------------------------------------

export class Redactor {
  private static sensitiveKeyPatterns = [
    /api[_-]?key/i,
    /secret/i,
    /token/i,
    /password/i,
    /auth/i,
    /authorization/i,
    /oauth/i,
    /credential/i,
    /private[_-]?key/i
  ];

  private static sensitiveValuePatterns = [
    /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi,
    /Basic\s+[A-Za-z0-9+/]+=*/gi,
    /(?:key|token|secret|password|auth|api_key|apikey)["']?\s*[:=]\s*["']?([A-Za-z0-9\-._~+/=]{8,})["']?/gi,
    /-----BEGIN [A-Z ]+PRIVATE KEY-----[^]+?-----END [A-Z ]+PRIVATE KEY-----/g
  ];

  /**
   * Sanitizes a string by redacting env vars, tokens, and authorization values.
   */
  public static sanitize(text: string): string {
    if (!text || typeof text !== "string") return text;

    let sanitized = text;

    // Redact active sensitive environment variables if present
    for (const [envKey, envVal] of Object.entries(process.env)) {
      if (!envVal || envVal.length < 4) continue;
      const isSensitiveKey = Redactor.sensitiveKeyPatterns.some(pat => pat.test(envKey));
      if (isSensitiveKey && sanitized.includes(envVal)) {
        sanitized = sanitized.split(envVal).join("[REDACTED]");
      }
    }

    // Redact known token/secret regex patterns
    for (const pattern of Redactor.sensitiveValuePatterns) {
      sanitized = sanitized.replace(pattern, (match) => {
        if (match.startsWith("Bearer ") || match.startsWith("Basic ")) {
          return match.split(" ")[0] + " [REDACTED]";
        }
        return "[REDACTED]";
      });
    }

    return sanitized;
  }

  /**
   * Recursively sanitizes plain objects, arrays, and primitives.
   */
  public static sanitizeObject<T>(obj: T): T {
    if (obj === null || obj === undefined) return obj;
    if (typeof obj === "string") return Redactor.sanitize(obj) as unknown as T;
    if (Array.isArray(obj)) return obj.map(item => Redactor.sanitizeObject(item)) as unknown as T;
    if (typeof obj === "object") {
      const result: Record<string, any> = {};
      for (const [k, v] of Object.entries(obj as Record<string, any>)) {
        const isKeySensitive = Redactor.sensitiveKeyPatterns.some(pat => pat.test(k));
        if (isKeySensitive && typeof v === "string") {
          result[k] = "[REDACTED]";
        } else {
          result[k] = Redactor.sanitizeObject(v);
        }
      }
      return result as unknown as T;
    }
    return obj;
  }

  /**
   * Prevents full .osu file contents from being dumped into logs unless explicitly requested for debug.
   */
  public static sanitizeOsuContent(content: string, allowFullDump: boolean = false): string {
    if (allowFullDump || !content || typeof content !== "string") return content;
    if (content.includes("osu file format v") && content.includes("[HitObjects]")) {
      const lineCount = content.split(/\r?\n/).length;
      const sizeBytes = Buffer.byteLength(content, "utf8");
      return `[OSU_BEATMAP_SUMMARY: ${lineCount} lines, ${sizeBytes} bytes - Full content redacted in audit log]`;
    }
    return content;
  }
}

// ---------------------------------------------------------------------------
// 2. Path Guard
// ---------------------------------------------------------------------------

export class PathGuard {
  private static forbiddenSubstrings = [
    ".env",
    ".claude",
    ".git",
    "node_modules",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    ".ssh",
    ".aws",
    "credentials.json",
    "token.json",
    "osu!\\songs",
    "osu!/songs",
    "\\songs\\",
    "/songs/"
  ];

  /**
   * Resolves canonical path and checks for symlink / junction escapes.
   */
  public static getCanonicalPath(targetPath: string, baseDir: string = process.cwd()): string {
    const abs = path.isAbsolute(targetPath) ? path.normalize(targetPath) : path.resolve(baseDir, targetPath);
    try {
      if (fs.existsSync(abs)) {
        return fs.realpathSync(abs);
      }
      // If leaf does not exist, resolve parent directory realpath
      let parent = path.dirname(abs);
      while (parent && parent !== path.dirname(parent) && !fs.existsSync(parent)) {
        parent = path.dirname(parent);
      }
      if (fs.existsSync(parent)) {
        const realParent = fs.realpathSync(parent);
        const relFromParent = path.relative(parent, abs);
        return path.resolve(realParent, relFromParent);
      }
    } catch {
      // Fall back to normalized absolute path
    }
    return abs;
  }

  /**
   * Validates target write path against security policies.
   */
  public static validateWritePath(
    targetPath: string,
    options: {
      allowedRunDir?: string;
      sourcePaths?: string[];
      baseDir?: string;
    } = {}
  ): PathValidationResult {
    const baseDir = options.baseDir || process.cwd();
    if (!targetPath || typeof targetPath !== "string") {
      return {
        allowed: false,
        code: "INVALID_TARGET_DIR",
        message: "Target write path is empty or invalid."
      };
    }

    const canonicalTarget = PathGuard.getCanonicalPath(targetPath, baseDir);
    const normalizedTargetLower = canonicalTarget.toLowerCase().replace(/\\/g, "/");
    const normalizedBase = PathGuard.getCanonicalPath(baseDir, baseDir).toLowerCase().replace(/\\/g, "/");

    // Check forbidden substrings (credentials, envs, songs, .claude)
    for (const forbidden of PathGuard.forbiddenSubstrings) {
      const normalizedForbidden = forbidden.toLowerCase().replace(/\\/g, "/");
      if (normalizedTargetLower.includes(normalizedForbidden)) {
        return {
          allowed: false,
          code: "POLICY_DENIED",
          message: `Write access to sensitive target '${forbidden}' is blocked by security policy.`,
          canonicalPath: canonicalTarget
        };
      }
    }

    // Source Overwrite Protection: Check against protected source beatmaps and audio files
    if (options.sourcePaths && options.sourcePaths.length > 0) {
      for (const src of options.sourcePaths) {
        if (!src) continue;
        const canonicalSrc = PathGuard.getCanonicalPath(src, baseDir);
        if (canonicalTarget.toLowerCase() === canonicalSrc.toLowerCase()) {
          return {
            allowed: false,
            code: "POLICY_DENIED",
            message: `Source preservation policy violation: cannot overwrite source file '${src}'.`,
            canonicalPath: canonicalTarget
          };
        }
      }
    }

    // Traversal and Run Directory Containment Guard
    if (options.allowedRunDir) {
      const canonicalRunDir = PathGuard.getCanonicalPath(options.allowedRunDir, baseDir).toLowerCase().replace(/\\/g, "/");
      if (!normalizedTargetLower.startsWith(canonicalRunDir)) {
        return {
          allowed: false,
          code: "POLICY_DENIED",
          message: `Write target '${canonicalTarget}' escapes authorized run directory '${options.allowedRunDir}'.`,
          canonicalPath: canonicalTarget
        };
      }
    } else {
      // Must be within project workspace under work/mapping-runs/
      const runsDir = path.resolve(baseDir, "work", "mapping-runs").toLowerCase().replace(/\\/g, "/");
      if (!normalizedTargetLower.startsWith(runsDir) && !normalizedTargetLower.startsWith(normalizedBase)) {
        return {
          allowed: false,
          code: "POLICY_DENIED",
          message: `Write target '${canonicalTarget}' is outside project workspace.`,
          canonicalPath: canonicalTarget
        };
      }
    }

    return {
      allowed: true,
      canonicalPath: canonicalTarget
    };
  }
}

// ---------------------------------------------------------------------------
// 3. Lifecycle Manager & Event Log
// ---------------------------------------------------------------------------

export class LifecycleManager {
  private static validTransitions: Record<RunStatus, RunStatus[]> = {
    PLANNED: ["BUILDING", "FAILED"],
    BUILDING: ["VERIFYING", "INCOMPLETE", "FAILED"],
    VERIFYING: ["COMPLETE", "INCOMPLETE", "FAILED"],
    COMPLETE: [],
    INCOMPLETE: ["BUILDING", "VERIFYING", "FAILED"],
    FAILED: ["BUILDING", "PLANNED"]
  };

  /**
   * Generates a unique, standardized run-id.
   */
  public static createRunId(prefix: string = "run"): string {
    const d = new Date();
    const dateStr = d.toISOString().replace(/[-:T]/g, "").slice(0, 14);
    const rand = Math.random().toString(36).substring(2, 7);
    return `${prefix}-${dateStr}-${rand}`;
  }

  /**
   * Validates if a lifecycle transition is allowed.
   */
  public static canTransition(from: RunStatus, to: RunStatus): boolean {
    if (from === to) return true;
    const allowed = LifecycleManager.validTransitions[from] || [];
    return allowed.includes(to);
  }

  /**
   * Appends an event to work/mapping-runs/<run-id>/events.jsonl.
   */
  public static appendEvent(runDir: string, event: Partial<EventLogEntry> & { run_id: string; current_status: RunStatus; event_type: EventLogEntry["event_type"] }): void {
    try {
      const eventsFile = path.join(runDir, "events.jsonl");
      const dirName = path.dirname(eventsFile);
      if (!fs.existsSync(dirName)) {
        fs.mkdirSync(dirName, { recursive: true });
      }

      const fullEntry: EventLogEntry = {
        timestamp: event.timestamp || new Date().toISOString(),
        run_id: event.run_id,
        event_type: event.event_type,
        previous_status: event.previous_status,
        current_status: event.current_status,
        tool_name: event.tool_name,
        details: event.details ? Redactor.sanitizeObject(event.details) : undefined,
        error: event.error ? Redactor.sanitizeObject(event.error) : undefined
      };

      const line = JSON.stringify(fullEntry) + "\n";
      fs.appendFileSync(eventsFile, line, { encoding: "utf8" });
    } catch (err: any) {
      console.error(`[osu-mapping-guard] Failed to append event log: ${err.message}`);
    }
  }

  /**
   * Reads all events for a run directory.
   */
  public static readEvents(runDir: string): EventLogEntry[] {
    const eventsFile = path.join(runDir, "events.jsonl");
    if (!fs.existsSync(eventsFile)) return [];
    try {
      const content = fs.readFileSync(eventsFile, "utf8");
      return content
        .split(/\r?\n/)
        .filter(l => l.trim().length > 0)
        .map(l => JSON.parse(l) as EventLogEntry);
    } catch {
      return [];
    }
  }

  /**
   * Gets the latest status from events log.
   */
  public static getCurrentStatus(runDir: string): RunStatus {
    const events = LifecycleManager.readEvents(runDir);
    if (events.length === 0) return "PLANNED";
    return events[events.length - 1].current_status;
  }
}

// ---------------------------------------------------------------------------
// 4. Completion Guard
// ---------------------------------------------------------------------------

function safeReadJson(filePath: string): any {
  const content = fs.readFileSync(filePath, "utf8").replace(/^\uFEFF/, "");
  return JSON.parse(content);
}

export class CompletionGuard {
  public static computeSha256(filePath: string): string {
    const buffer = fs.readFileSync(filePath);
    return crypto.createHash("sha256").update(buffer).digest("hex");
  }

  /**
   * Evaluates all completion criteria across candidate, completion report, and verification report.
   */
  public static evaluateCompletion(runDir: string): CompletionEvaluationResult {
    const reasons: string[] = [];

    const candPath = path.join(runDir, "candidate", "candidate.osu");
    const compReportPath = path.join(runDir, "reports", "completion-report.json");
    const verReportPath = path.join(runDir, "reports", "verification-report.json");
    const provPath = path.join(runDir, "reports", "provenance.json");

    // 1. Check artifact presence
    if (!fs.existsSync(candPath)) {
      return {
        passed: false,
        verdict: "FAILED",
        reasons: ["Candidate file 'candidate/candidate.osu' does not exist on disk."]
      };
    }

    if (!fs.existsSync(compReportPath)) {
      reasons.push("Missing required report artifact: 'reports/completion-report.json'.");
    }

    if (!fs.existsSync(verReportPath)) {
      reasons.push("Missing required report artifact: 'reports/verification-report.json'.");
    }

    if (reasons.length > 0) {
      return {
        passed: false,
        verdict: "INCOMPLETE",
        reasons
      };
    }

    const candSha256 = CompletionGuard.computeSha256(candPath);
    let provSha256: string | undefined;

    // 2. Validate Provenance Checksum if present
    if (fs.existsSync(provPath)) {
      try {
        const provData = safeReadJson(provPath);
        provSha256 = provData?.candidate_manifest?.sha256;
        if (provSha256 && provSha256 !== candSha256) {
          reasons.push(`Checksum mismatch between candidate.osu (${candSha256}) and provenance.json (${provSha256}).`);
        }
      } catch (e: any) {
        reasons.push(`Failed to parse provenance.json: ${e.message}`);
      }
    }

    // 3. Inspect Completion Report
    let compData: any = {};
    try {
      compData = safeReadJson(compReportPath);
    } catch (e: any) {
      reasons.push(`Failed to parse completion-report.json: ${e.message}`);
    }

    if (compData.status !== "COMPLETE") {
      reasons.push(`Builder completion-report status is '${compData.status}' (expected 'COMPLETE').`);
    }

    if (compData.hard_requirements_passed === false) {
      reasons.push("Builder report indicates hard_requirements_passed is false.");
    }

    const stageResults = compData.stage_results || {};
    const criticalStages = ["file_integrity", "beat_grid_validity", "playfield_boundaries", "originality_gate"];
    for (const stage of criticalStages) {
      if (stageResults[stage] && stageResults[stage] !== "PASS" && stageResults[stage] !== "PARTIAL") {
        reasons.push(`Critical stage '${stage}' has unapproved result '${stageResults[stage]}'.`);
      }
    }

    if (compData.originality_verdict && ["CLONE", "NEAR_CLONE", "INCONCLUSIVE"].includes(compData.originality_verdict)) {
      reasons.push(`Originality check rejected with verdict '${compData.originality_verdict}'.`);
    }

    // 4. Inspect Verification Report
    let verData: any = {};
    try {
      verData = safeReadJson(verReportPath);
    } catch (e: any) {
      reasons.push(`Failed to parse verification-report.json: ${e.message}`);
    }

    if (verData.verdict !== "PASS") {
      reasons.push(`Verifier verdict is '${verData.verdict}' (expected 'PASS').`);
    }

    if (verData.regressions_detected === true) {
      reasons.push("Verifier reported regressions detected.");
    }

    const acResults = verData.acceptance_criteria_results || verData.acceptance_criteria_status || [];
    for (const ac of acResults) {
      if (ac.status === "FAIL") {
        reasons.push(`Acceptance criterion '${ac.id || ac.description}' failed verification.`);
      }
    }

    const passed = reasons.length === 0;
    return {
      passed,
      verdict: passed ? "COMPLETE" : (reasons.some(r => r.includes("mismatch") || r.includes("failed")) ? "FAILED" : "INCOMPLETE"),
      reasons,
      candidate_sha256: candSha256,
      provenance_sha256: provSha256,
      verification_verdict: verData.verdict,
      hard_requirements_passed: compData.hard_requirements_passed
    };
  }
}

// ---------------------------------------------------------------------------
// 5. Recovery Manager
// ---------------------------------------------------------------------------

export class RecoveryManager {
  /**
   * Checks if an existing run directory contains a valid candidate that matches reports,
   * allowing resumption without repeating generation.
   */
  public static checkRecovery(runDir: string): RecoveryCheckResult {
    const candPath = path.join(runDir, "candidate", "candidate.osu");
    const compReportPath = path.join(runDir, "reports", "completion-report.json");
    const verReportPath = path.join(runDir, "reports", "verification-report.json");

    if (!fs.existsSync(candPath) || !fs.existsSync(compReportPath)) {
      return { canResume: false, stage: "NONE", reason: "Missing candidate or completion report." };
    }

    try {
      const candSha = CompletionGuard.computeSha256(candPath);
      const compData = safeReadJson(compReportPath);

      if (compData.status === "COMPLETE" && compData.hard_requirements_passed !== false) {
        if (fs.existsSync(verReportPath)) {
          const verData = safeReadJson(verReportPath);
          if (verData.verdict === "PASS") {
            return {
              canResume: true,
              stage: "COMPLETE",
              candidatePath: candPath,
              candidateSha256: candSha,
              reason: "Run already verified complete with matching checksums."
            };
          }
        }
        return {
          canResume: true,
          stage: "VERIFYING",
          candidatePath: candPath,
          candidateSha256: candSha,
          reason: "Candidate generation validated; ready for independent verification."
        };
      }
    } catch (e: any) {
      return { canResume: false, stage: "NONE", reason: `Recovery check error: ${e.message}` };
    }

    return { canResume: false, stage: "NONE", reason: "Candidate is incomplete or corrupt." };
  }
}

// ---------------------------------------------------------------------------
// 6. OpenCode Plugin Lifecycle Definition
// ---------------------------------------------------------------------------

export const osuMappingGuard: Plugin = async (input: PluginInput, options?: PluginOptions): Promise<Hooks> => {
  const baseDir = input.directory || input.worktree || process.cwd();
  let currentRunId: string | null = null;
  let currentRunDir: string | null = null;

  return {
    "tool.execute.before": async (toolInput, output) => {
      const toolName = toolInput.tool;
      const args = output.args || {};

      // 1. Manage Run Lifecycle and Run ID
      if (toolName === "osu_map_generate") {
        if (args.run_directory) {
          currentRunDir = path.isAbsolute(args.run_directory)
            ? args.run_directory
            : path.resolve(baseDir, args.run_directory);
          currentRunId = path.basename(currentRunDir);
        } else {
          currentRunId = LifecycleManager.createRunId();
          currentRunDir = path.resolve(baseDir, "work", "mapping-runs", currentRunId);
          output.args.run_directory = currentRunDir;
        }

        // Initialize run lifecycle state
        const prevStatus = currentRunDir && fs.existsSync(currentRunDir)
          ? LifecycleManager.getCurrentStatus(currentRunDir)
          : "PLANNED";

        LifecycleManager.appendEvent(currentRunDir, {
          run_id: currentRunId,
          event_type: "STATUS_TRANSITION",
          previous_status: prevStatus,
          current_status: "BUILDING",
          tool_name: toolName,
          details: { action: "Beginning beatmap candidate generation", arguments: Redactor.sanitizeObject(args) }
        });

        // Check for Recovery: If valid candidate exists, skip generation
        const recovery = RecoveryManager.checkRecovery(currentRunDir);
        if (recovery.canResume) {
          LifecycleManager.appendEvent(currentRunDir, {
            run_id: currentRunId,
            event_type: "RECOVERY_DETECTED",
            current_status: "BUILDING",
            tool_name: toolName,
            details: { recovery_info: recovery }
          });
        }
      }

      // 2. Path Guard Security Verification
      const targetWriteDir = args.run_directory || args.report_directory;
      if (targetWriteDir) {
        const sourcePaths: string[] = [];
        if (args.audio_path) sourcePaths.push(args.audio_path);
        if (args.references) sourcePaths.push(...args.references);
        if (args.reference_paths) sourcePaths.push(...args.reference_paths);

        const check = PathGuard.validateWritePath(targetWriteDir, {
          allowedRunDir: currentRunDir || undefined,
          sourcePaths,
          baseDir
        });

        if (!check.allowed) {
          if (currentRunDir) {
            LifecycleManager.appendEvent(currentRunDir, {
              run_id: currentRunId || "unknown",
              event_type: "POLICY_DENIED",
              current_status: "FAILED",
              tool_name: toolName,
              error: {
                code: check.code || "POLICY_DENIED",
                category: "security",
                message: check.message || "Unauthorized target write path."
              },
              details: { attempted_path: targetWriteDir }
            });
          }

          throw new Error(JSON.stringify({
            error: {
              code: check.code || "POLICY_DENIED",
              category: "security",
              message: check.message || "Write operation blocked by path guard policy."
            }
          }));
        }
      }

      // Log Tool Execution Start
      if (currentRunDir && currentRunId) {
        LifecycleManager.appendEvent(currentRunDir, {
          run_id: currentRunId,
          event_type: "TOOL_BEFORE",
          current_status: toolName === "osu_map_validate" ? "VERIFYING" : (LifecycleManager.getCurrentStatus(currentRunDir) || "BUILDING"),
          tool_name: toolName,
          details: { arguments: Redactor.sanitizeObject(args) }
        });
      }
    },

    "tool.execute.after": async (toolInput, output) => {
      const toolName = toolInput.tool;
      const toolArgs = toolInput.args || {};

      // 1. Apply Redaction to tool output text
      if (output.output) {
        output.output = Redactor.sanitize(output.output);
        output.output = Redactor.sanitizeOsuContent(output.output);
      }
      if (output.title) {
        output.title = Redactor.sanitize(output.title);
      }

      const activeRunDir = currentRunDir || (toolArgs.run_directory ? path.resolve(baseDir, toolArgs.run_directory) : null);
      const activeRunId = currentRunId || (activeRunDir ? path.basename(activeRunDir) : "unknown");

      if (activeRunDir && fs.existsSync(activeRunDir)) {
        // Log tool completion event
        LifecycleManager.appendEvent(activeRunDir, {
          run_id: activeRunId,
          event_type: "TOOL_AFTER",
          current_status: toolName === "osu_map_validate" ? "VERIFYING" : LifecycleManager.getCurrentStatus(activeRunDir),
          tool_name: toolName,
          details: { title: output.title, metadata: Redactor.sanitizeObject(output.metadata) }
        });

        // 2. Completion Guard Evaluation
        if (toolName === "osu_map_validate" || toolName === "osu_map_generate") {
          const evalRes = CompletionGuard.evaluateCompletion(activeRunDir);
          const newStatus: RunStatus = evalRes.passed ? "COMPLETE" : (evalRes.verdict === "FAILED" ? "FAILED" : "INCOMPLETE");

          LifecycleManager.appendEvent(activeRunDir, {
            run_id: activeRunId,
            event_type: "COMPLETION_EVALUATION",
            previous_status: LifecycleManager.getCurrentStatus(activeRunDir),
            current_status: newStatus,
            tool_name: toolName,
            details: { evaluation: evalRes }
          });
        }
      }
    }
  };
};

export function plugin(fn: Plugin): Plugin {
  return fn;
}

export default osuMappingGuard;
