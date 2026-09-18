import { tool } from "@opencode-ai/plugin";
import * as path from "path";
import * as fs from "fs";
import { spawn } from "child_process";

export const osu_map_validate = tool({
  description: "Validates an osu! beatmap candidate against format integrity, beat-grid snapping, playfield bounds, song coverage, target difficulty, and anti-plagiarism originality gate.",
  args: {
    candidate_path: tool.schema.string().describe("Path to .osu beatmap candidate to validate"),
    report_directory: tool.schema.string().optional().describe("Directory where validation report should be written"),
    audio_path: tool.schema.string().optional().describe("Path to song audio file for duration/coverage validation"),
    references: tool.schema.array(tool.schema.string()).optional().describe("Array of reference .osu paths for originality comparison"),
    style: tool.schema.enum(["aimslop", "flow_aim", "hybrid"]).default("hybrid").describe("Expected mapping style"),
    target_star_min: tool.schema.number().optional().describe("Target minimum star rating"),
    target_star_max: tool.schema.number().optional().describe("Target maximum star rating")
  },
  async execute(args, context) {
    const baseDir = context.directory || context.worktree || process.cwd();
    const candAbs = path.isAbsolute(args.candidate_path)
      ? args.candidate_path
      : path.resolve(baseDir, args.candidate_path);

    if (!fs.existsSync(candAbs)) {
      return JSON.stringify({
        error: {
          code: "CANDIDATE_NOT_FOUND",
          category: "input",
          message: `Candidate file not found: ${candAbs}`,
          recoverable: false
        }
      }, null, 2);
    }

    const scriptPath = path.resolve(
      baseDir,
      ".opencode",
      "skills",
      "osu-mapping",
      "scripts",
      "validate_osu.py"
    );

    if (!fs.existsSync(scriptPath)) {
      return JSON.stringify({
        error: {
          code: "SCRIPT_NOT_FOUND",
          category: "engine",
          message: `Validation script not found at: ${scriptPath}`,
          recoverable: false
        }
      }, null, 2);
    }

    const pyArgs = [scriptPath, "--candidate", candAbs, "--style", args.style || "hybrid"];

    if (args.report_directory) {
      const repAbs = path.isAbsolute(args.report_directory)
        ? args.report_directory
        : path.resolve(baseDir, args.report_directory);
      pyArgs.push("--report-dir", repAbs);
    }

    if (args.audio_path) {
      const audioAbs = path.isAbsolute(args.audio_path)
        ? args.audio_path
        : path.resolve(baseDir, args.audio_path);
      if (fs.existsSync(audioAbs)) {
        pyArgs.push("--audio", audioAbs);
      }
    }

    if (args.target_star_min !== undefined) pyArgs.push("--target-star-min", String(args.target_star_min));
    if (args.target_star_max !== undefined) pyArgs.push("--target-star-max", String(args.target_star_max));

    if (args.references && args.references.length > 0) {
      pyArgs.push("--references");
      for (const ref of args.references) {
        const refAbs = path.isAbsolute(ref) ? ref : path.resolve(baseDir, ref);
        if (fs.existsSync(refAbs)) {
          pyArgs.push(refAbs);
        }
      }
    }

    return new Promise((resolve) => {
      const proc = spawn("python", pyArgs, {
        cwd: baseDir,
        windowsHide: true
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
      });

      proc.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });

      proc.on("close", (code) => {
        try {
          const parsed = JSON.parse(stdout.trim());
          resolve(JSON.stringify(parsed, null, 2));
        } catch {
          resolve(JSON.stringify({
            exit_code: code,
            stdout: stdout.trim(),
            stderr: stderr.trim(),
            verdict: code === 0 ? "PASS" : "FAIL"
          }, null, 2));
        }
      });

      proc.on("error", (err) => {
        resolve(JSON.stringify({
          error: {
            code: "SPAWN_ERROR",
            category: "process",
            message: err.message,
            recoverable: false
          }
        }, null, 2));
      });
    });
  }
});

export default osu_map_validate;
