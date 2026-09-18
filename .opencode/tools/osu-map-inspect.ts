import { tool } from "@opencode-ai/plugin";
import * as path from "path";
import * as fs from "fs";
import * as crypto from "crypto";
import { execFile } from "child_process";

interface InspectResult {
  file_path: string;
  kind: "osu" | "audio" | "unknown";
  exists: boolean;
  size_bytes: number;
  sha256: string;
  osu_details?: {
    format_version: number;
    general: Record<string, string>;
    metadata: Record<string, string>;
    difficulty: Record<string, number>;
    timing_points_count: number;
    uninherited_timing_points: Array<{ time_ms: number; bpm: number; meter: number }>;
    hit_objects_count: {
      circles: number;
      sliders: number;
      spinners: number;
      total: number;
    };
    time_range_ms: {
      first_object: number;
      last_object: number;
      duration_ms: number;
    };
    playfield_bounds: {
      min_x: number;
      max_x: number;
      min_y: number;
      max_y: number;
      within_standard_bounds: boolean;
    };
  };
  audio_details?: {
    filename: string;
    duration_ms: number | "unknown";
    bitrate: string | "unknown";
    channels: number | "unknown";
  };
  errors?: string[];
}

function computeSha256(filePath: string): string {
  const buffer = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function parseOsuContent(content: string, filePath: string): InspectResult["osu_details"] {
  const lines = content.split(/\r?\n/);
  let formatVersion = 14;
  const versionMatch = lines[0]?.match(/osu file format v(\d+)/i);
  if (versionMatch) {
    formatVersion = parseInt(versionMatch[1], 10);
  }

  let currentSection = "";
  const general: Record<string, string> = {};
  const metadata: Record<string, string> = {};
  const difficulty: Record<string, number> = {};
  const uninherited: Array<{ time_ms: number; bpm: number; meter: number }> = [];
  let timingPointsCount = 0;

  let circles = 0;
  let sliders = 0;
  let spinners = 0;
  let minTime = Infinity;
  let maxTime = -Infinity;
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("//")) continue;

    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      currentSection = trimmed.slice(1, -1);
      continue;
    }

    if (currentSection === "General") {
      const idx = trimmed.indexOf(":");
      if (idx !== -1) {
        general[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
      }
    } else if (currentSection === "Metadata") {
      const idx = trimmed.indexOf(":");
      if (idx !== -1) {
        metadata[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
      }
    } else if (currentSection === "Difficulty") {
      const idx = trimmed.indexOf(":");
      if (idx !== -1) {
        const key = trimmed.slice(0, idx).trim();
        const val = parseFloat(trimmed.slice(idx + 1).trim());
        if (!isNaN(val)) difficulty[key] = val;
      }
    } else if (currentSection === "TimingPoints") {
      const parts = trimmed.split(",");
      if (parts.length >= 2) {
        timingPointsCount++;
        const timeMs = Math.round(parseFloat(parts[0]));
        const beatLen = parseFloat(parts[1]);
        const meter = parts.length > 2 ? parseInt(parts[2], 10) || 4 : 4;
        const uninh = parts.length > 6 ? parts[6].trim() === "1" : beatLen > 0;
        if (uninh && beatLen > 0) {
          uninherited.push({
            time_ms: timeMs,
            bpm: Math.round((60000.0 / beatLen) * 100) / 100,
            meter: meter
          });
        }
      }
    } else if (currentSection === "HitObjects") {
      const parts = trimmed.split(",");
      if (parts.length >= 4) {
        const x = parseFloat(parts[0]);
        const y = parseFloat(parts[1]);
        const time = parseInt(parts[2], 10);
        const type = parseInt(parts[3], 10);

        if (!isNaN(x) && !isNaN(y)) {
          minX = Math.min(minX, x);
          maxX = Math.max(maxX, x);
          minY = Math.min(minY, y);
          maxY = Math.max(maxY, y);
        }

        if (!isNaN(time)) {
          minTime = Math.min(minTime, time);
          maxTime = Math.max(maxTime, time);
        }

        if (type & 1) circles++;
        else if (type & 2) {
          sliders++;
          // Parse slider repeat count and duration if present
        } else if (type & 8) spinners++;
      }
    }
  }

  const total = circles + sliders + spinners;
  const standardBounds = minX >= 0 && maxX <= 512 && minY >= 0 && maxY <= 384;

  return {
    format_version: formatVersion,
    general,
    metadata,
    difficulty,
    timing_points_count: timingPointsCount,
    uninherited_timing_points: uninherited,
    hit_objects_count: {
      circles,
      sliders,
      spinners,
      total
    },
    time_range_ms: {
      first_object: isFinite(minTime) ? minTime : 0,
      last_object: isFinite(maxTime) ? maxTime : 0,
      duration_ms: isFinite(maxTime) && isFinite(minTime) ? maxTime - minTime : 0
    },
    playfield_bounds: {
      min_x: isFinite(minX) ? minX : 0,
      max_x: isFinite(maxX) ? maxX : 0,
      min_y: isFinite(minY) ? minY : 0,
      max_y: isFinite(maxY) ? maxY : 0,
      within_standard_bounds: total > 0 ? standardBounds : true
    }
  };
}

export const osu_map_inspect = tool({
  description: "Inspects an osu! beatmap (.osu) or audio file and returns a structured JSON inspection report with timing points, difficulty parameters, object counts, playfield bounds, and SHA-256 hash.",
  args: {
    path: tool.schema.string().describe("Path to .osu beatmap or audio file (relative or absolute)"),
    kind: tool.schema.enum(["osu", "audio", "auto"]).default("auto").describe("File format kind ('osu', 'audio', or 'auto')"),
    include_audio_metadata: tool.schema.boolean().default(false).describe("Whether to attempt audio duration/metadata inspection")
  },
  async execute(args, context) {
    const baseDir = context.directory || context.worktree || process.cwd();
    const targetPath = path.isAbsolute(args.path) ? args.path : path.resolve(baseDir, args.path);

    // Security check: reject access to sensitive files
    const normalizedTarget = path.normalize(targetPath);
    if (normalizedTarget.includes(".env") || normalizedTarget.includes("id_rsa")) {
      return JSON.stringify({
        error: {
          code: "ACCESS_DENIED",
          category: "security",
          message: "Access to credentials, tokens, or environment files is denied.",
          recoverable: false
        }
      }, null, 2);
    }

    if (!fs.existsSync(normalizedTarget)) {
      return JSON.stringify({
        error: {
          code: "FILE_NOT_FOUND",
          category: "input",
          message: `Target file does not exist: ${normalizedTarget}`,
          recoverable: false
        }
      }, null, 2);
    }

    const stat = fs.statSync(normalizedTarget);
    const sizeBytes = stat.size;
    const sha256 = computeSha256(normalizedTarget);

    let detectedKind = args.kind || "auto";
    if (detectedKind === "auto") {
      const ext = path.extname(normalizedTarget).toLowerCase();
      if (ext === ".osu") detectedKind = "osu";
      else if ([".mp3", ".wav", ".ogg", ".flac", ".m4a"].includes(ext)) detectedKind = "audio";
      else detectedKind = "osu";
    }

    const result: InspectResult = {
      file_path: normalizedTarget,
      kind: detectedKind as "osu" | "audio",
      exists: true,
      size_bytes: sizeBytes,
      sha256: sha256
    };

    if (detectedKind === "osu") {
      try {
        const content = fs.readFileSync(normalizedTarget, "utf-8");
        result.osu_details = parseOsuContent(content, normalizedTarget);
      } catch (err: any) {
        result.errors = [err.message || "Failed to parse osu file"];
      }
    } else if (detectedKind === "audio") {
      result.audio_details = {
        filename: path.basename(normalizedTarget),
        duration_ms: "unknown",
        bitrate: "unknown",
        channels: "unknown"
      };
    }

    return JSON.stringify(result, null, 2);
  }
});

export default osu_map_inspect;
