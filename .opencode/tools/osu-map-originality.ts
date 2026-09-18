import { tool } from "@opencode-ai/plugin";
import * as path from "path";
import * as fs from "fs";
import { spawn } from "child_process";

export const osu_map_originality = tool({
  description: "Checks an osu! beatmap candidate against reference maps for plagiarism, n-gram sequence matching, rhythm Jaccard index, and trajectory correlation.",
  args: {
    candidate_path: tool.schema.string().describe("Path to candidate .osu beatmap file"),
    reference_paths: tool.schema.array(tool.schema.string()).describe("List of reference .osu beatmap paths to compare against")
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

    if (!args.reference_paths || args.reference_paths.length === 0) {
      return JSON.stringify({
        error: {
          code: "NO_REFERENCES",
          category: "input",
          message: "At least one reference beatmap path is required for originality verification.",
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
      "check_originality.py"
    );

    if (!fs.existsSync(scriptPath)) {
      return JSON.stringify({
        error: {
          code: "SCRIPT_NOT_FOUND",
          category: "engine",
          message: `Originality script not found at: ${scriptPath}`,
          recoverable: false
        }
      }, null, 2);
    }

    const pyArgs = [scriptPath, "--candidate", candAbs, "--references"];
    for (const ref of args.reference_paths) {
      const refAbs = path.isAbsolute(ref) ? ref : path.resolve(baseDir, ref);
      if (fs.existsSync(refAbs)) {
        pyArgs.push(refAbs);
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
            stderr: stderr.trim()
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

export default osu_map_originality;
