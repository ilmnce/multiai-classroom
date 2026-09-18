import { tool } from "@opencode-ai/plugin";
import * as path from "path";
import * as fs from "fs";
import { spawn } from "child_process";

export const osu_map_generate = tool({
  description: "Generates a fully playable osu! beatmap candidate and completion report in a designated run directory using the 2-pass mapping engine.",
  args: {
    run_directory: tool.schema.string().describe("Target run directory (e.g. 'work/mapping-runs/run-01')"),
    mapping_plan_path: tool.schema.string().optional().describe("Path to mapping-plan.json artifact"),
    audio_path: tool.schema.string().optional().describe("Path to song audio file"),
    bpm: tool.schema.number().optional().describe("Song BPM"),
    offset_ms: tool.schema.number().optional().describe("First beat offset in milliseconds"),
    duration_ms: tool.schema.number().optional().describe("Total duration in milliseconds"),
    style: tool.schema.enum(["aimslop", "flow_aim", "hybrid"]).optional().describe("Mapping style taxonomy"),
    target_star_min: tool.schema.number().optional().describe("Minimum target star rating"),
    target_star_max: tool.schema.number().optional().describe("Maximum target star rating")
  },
  async execute(args, context) {
    const baseDir = context.directory || context.worktree || process.cwd();
    const runDir = path.isAbsolute(args.run_directory)
      ? args.run_directory
      : path.resolve(baseDir, args.run_directory);

    // Path Guard: Prevent write escaping into unauthorized directories
    const normalizedRunDir = path.normalize(runDir);
    const normalizedBase = path.normalize(baseDir);

    if (
      normalizedRunDir.includes(".env") ||
      normalizedRunDir.includes("node_modules") ||
      normalizedRunDir.includes(".git")
    ) {
      return JSON.stringify({
        error: {
          code: "INVALID_TARGET_DIR",
          category: "security",
          message: "Run directory target is forbidden.",
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
      "generate_osu.py"
    );

    if (!fs.existsSync(scriptPath)) {
      return JSON.stringify({
        error: {
          code: "SCRIPT_NOT_FOUND",
          category: "engine",
          message: `Mapping generator script not found at: ${scriptPath}`,
          recoverable: false
        }
      }, null, 2);
    }

    const pyArgs = [scriptPath, "--output-dir", normalizedRunDir];

    if (args.mapping_plan_path) {
      const planAbs = path.isAbsolute(args.mapping_plan_path)
        ? args.mapping_plan_path
        : path.resolve(baseDir, args.mapping_plan_path);
      if (fs.existsSync(planAbs)) {
        pyArgs.push("--plan", planAbs);
      }
    }

    if (args.audio_path) {
      const audioAbs = path.isAbsolute(args.audio_path)
        ? args.audio_path
        : path.resolve(baseDir, args.audio_path);
      pyArgs.push("--audio", audioAbs);
    }

    if (args.bpm !== undefined) pyArgs.push("--bpm", String(args.bpm));
    if (args.offset_ms !== undefined) pyArgs.push("--offset", String(args.offset_ms));
    if (args.duration_ms !== undefined) pyArgs.push("--duration", String(args.duration_ms));
    if (args.style) pyArgs.push("--style", args.style);
    if (args.target_star_min !== undefined) pyArgs.push("--target-star-min", String(args.target_star_min));
    if (args.target_star_max !== undefined) pyArgs.push("--target-star-max", String(args.target_star_max));

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
            status: code === 0 ? "COMPLETE" : "FAILED"
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

export default osu_map_generate;
