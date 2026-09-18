#!/usr/bin/env python3
"""
cursor_simulator.py - Cursor Motion Simulation and Difficulty Estimation for osu!

Purpose:
  Simulates cursor trajectory across hit objects to evaluate:
  - Movement velocities, accelerations, and angular changes
  - Aim and Speed difficulty ratings (Star Rating approximation)
  - Playability heuristics (impossible snaps, strain spikes, boundary clipping)

Usage:
  python cursor_simulator.py --file candidate.osu
  python cursor_simulator.py --json-input objects.json

Exit Codes:
  0: Success / Playable
  1: Playability failure (impossible snaps, severe strain anomalies)
  2: Input error
"""

import sys
import os
import json
import math
import argparse
from typing import List, Dict, Any, Tuple, Optional


def parse_osu_hit_objects(osu_lines: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Parses [Difficulty] and [HitObjects] sections from an .osu file."""
    diff_settings: Dict[str, float] = {
        "CS": 4.0,
        "AR": 9.0,
        "OD": 8.0,
        "HP": 5.0,
        "SliderMultiplier": 1.4,
        "SliderTickRate": 1.0
    }

    in_diff = False
    in_ho = False
    raw_objects = []

    for line_raw in osu_lines:
        line = line_raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("[") and line.endswith("]"):
            sec = line[1:-1]
            in_diff = (sec == "Difficulty")
            in_ho = (sec == "HitObjects")
            continue

        if in_diff and ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k == "CircleSize":
                diff_settings["CS"] = float(v)
            elif k == "ApproachRate":
                diff_settings["AR"] = float(v)
            elif k == "OverallDifficulty":
                diff_settings["OD"] = float(v)
            elif k == "HPDrainRate":
                diff_settings["HP"] = float(v)
            elif k == "SliderMultiplier":
                diff_settings["SliderMultiplier"] = float(v)
            elif k == "SliderTickRate":
                diff_settings["SliderTickRate"] = float(v)

        elif in_ho:
            raw_objects.append(line)

    hit_objects = []
    for raw in raw_objects:
        parts = raw.split(",")
        if len(parts) < 4:
            continue
        try:
            x = float(parts[0])
            y = float(parts[1])
            t = int(float(parts[2]))
            obj_type = int(parts[3])
            hitsound = int(parts[4]) if len(parts) > 4 else 0

            is_circle = bool(obj_type & 1)
            is_slider = bool(obj_type & 2)
            is_spinner = bool(obj_type & 8)

            end_t = t
            end_x = x
            end_y = y

            if is_spinner and len(parts) > 5:
                try:
                    end_t = int(float(parts[5]))
                except ValueError:
                    end_t = t + 1000
            elif is_slider and len(parts) > 7:
                # Estimate slider endpoint from curve points if available
                curve_parts = parts[5].split("|")
                if len(curve_parts) > 1:
                    last_pt = curve_parts[-1].split(":")
                    if len(last_pt) == 2:
                        try:
                            end_x = float(last_pt[0])
                            end_y = float(last_pt[1])
                        except ValueError:
                            pass
                # Length & duration estimation
                try:
                    length = float(parts[7])
                    # rough duration: length / (SliderMultiplier * 100) * 333ms
                    slides = int(parts[6]) if len(parts) > 6 else 1
                    dur = (length / (diff_settings["SliderMultiplier"] * 100.0)) * 350.0 * slides
                    end_t = t + int(dur)
                except (ValueError, IndexError):
                    end_t = t + 250

            hit_objects.append({
                "x": x,
                "y": y,
                "time": t,
                "end_time": end_t,
                "end_x": end_x,
                "end_y": end_y,
                "type": obj_type,
                "is_circle": is_circle,
                "is_slider": is_slider,
                "is_spinner": is_spinner,
                "hitsound": hitsound
            })
        except Exception:
            continue

    hit_objects.sort(key=lambda o: o["time"])
    return hit_objects, diff_settings


def simulate_cursor_motion(
    hit_objects: List[Dict[str, Any]],
    diff_settings: Dict[str, float]
) -> Dict[str, Any]:
    """
    Simulates cursor motion, computing aim strain, speed strain, and Star Rating.
    """
    if not hit_objects:
        return {
            "playable": False,
            "star_rating": 0.0,
            "aim_rating": 0.0,
            "speed_rating": 0.0,
            "anomalies": ["No hit objects found"]
        }

    total_objs = len(hit_objects)
    aim_strains: List[float] = []
    speed_strains: List[float] = []
    velocities: List[float] = []
    anomalies: List[str] = []

    prev_obj = hit_objects[0]
    prev_vec: Optional[Tuple[float, float]] = None

    for i in range(1, total_objs):
        curr = hit_objects[i]
        dt = max(10, curr["time"] - prev_obj["end_time"])  # time available to move
        dx = curr["x"] - prev_obj["end_x"]
        dy = curr["y"] - prev_obj["end_y"]
        dist = math.hypot(dx, dy)
        vel = dist / (dt / 1000.0)  # pixels per second
        velocities.append(vel)

        # Boundary check
        if curr["x"] < 0 or curr["x"] > 512 or curr["y"] < 0 or curr["y"] > 384:
            anomalies.append(f"Object at {curr['time']}ms out of bounds: ({curr['x']}, {curr['y']})")

        # Impossible jump check (e.g. > 4500 px/s over < 80ms)
        if dt < 80 and vel > 4500:
            anomalies.append(f"Impossible snap at {curr['time']}ms: {vel:.0f} px/s in {dt}ms")

        # Angle calculation
        curr_vec = (dx, dy)
        angle_bonus = 1.0
        if prev_vec is not None and dist > 40:
            prev_dist = math.hypot(prev_vec[0], prev_vec[1])
            if prev_dist > 40:
                dot = (prev_vec[0] * curr_vec[0] + prev_vec[1] * curr_vec[1]) / (prev_dist * dist)
                dot = max(-1.0, min(1.0, dot))
                angle_rad = math.acos(dot)
                # Acute angles (snappy jumps) require more deceleration & acceleration
                if angle_rad < math.pi * 0.5:
                    angle_bonus = 1.0 + 0.35 * (1.0 - angle_rad / (math.pi * 0.5))

        # Aim strain model
        # Base aim depends on distance scaled by time
        aim_strain = (dist ** 1.1) / (dt ** 0.85) * angle_bonus * 0.85
        aim_strains.append(aim_strain)

        # Speed strain model (tapping density)
        # Fast 1/4 streams have small dt (< 150ms)
        speed_strain = (1000.0 / dt) ** 1.05 * 0.12
        speed_strains.append(speed_strain)

        prev_obj = curr
        prev_vec = curr_vec

    # Aggregate difficulty calculation (decayed moving average / top peak percentile)
    if aim_strains:
        aim_strains.sort(reverse=True)
        top_aim = aim_strains[:max(1, len(aim_strains) // 8)]
        aim_rating = (sum(top_aim) / len(top_aim)) * 0.22
        aim_rating = round(max(0.5, min(10.0, aim_rating)), 2)
    else:
        aim_rating = 1.0

    if speed_strains:
        speed_strains.sort(reverse=True)
        top_speed = speed_strains[:max(1, len(speed_strains) // 8)]
        speed_rating = (sum(top_speed) / len(top_speed)) * 0.20
        speed_rating = round(max(0.5, min(10.0, speed_rating)), 2)
    else:
        speed_rating = 1.0

    # Calibrate combined Star Rating
    combined_sr = (aim_rating ** 1.35 + speed_rating ** 1.35) ** (1.0 / 1.35) * 0.92
    # Scale slightly by CS and OD
    cs = diff_settings.get("CS", 4.0)
    cs_factor = 1.0 + (cs - 4.0) * 0.04
    star_rating = round(max(0.5, min(10.0, combined_sr * cs_factor)), 2)

    avg_vel = sum(velocities) / len(velocities) if velocities else 0.0
    max_vel = max(velocities) if velocities else 0.0

    is_playable = len(anomalies) == 0

    return {
        "playable": is_playable,
        "object_count": total_objs,
        "star_rating": star_rating,
        "aim_rating": aim_rating,
        "speed_rating": speed_rating,
        "difficulty_settings": diff_settings,
        "metrics": {
            "average_velocity_px_s": round(avg_vel, 1),
            "peak_velocity_px_s": round(max_vel, 1),
            "strain_sample_count": len(aim_strains)
        },
        "anomalies_count": len(anomalies),
        "anomalies": anomalies[:10]  # Show first 10
    }


def main():
    parser = argparse.ArgumentParser(description="osu! Cursor Simulator & Star Rating Estimator")
    parser.add_argument("--file", type=str, help="Path to .osu beatmap file to simulate")
    parser.add_argument("--json-input", type=str, help="Path to JSON file containing hit objects")

    args = parser.parse_args()

    try:
        if args.file:
            if not os.path.exists(args.file):
                sys.stderr.write(f"Error: File not found: {args.file}\n")
                sys.exit(2)
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            objects, diff = parse_osu_hit_objects(lines)
            sim_result = simulate_cursor_motion(objects, diff)
            sys.stdout.write(json.dumps(sim_result, indent=2) + "\n")
            sys.exit(0 if sim_result["playable"] else 1)

        elif args.json_input:
            if not os.path.exists(args.json_input):
                sys.stderr.write(f"Error: JSON file not found: {args.json_input}\n")
                sys.exit(2)
            with open(args.json_input, "r", encoding="utf-8") as f:
                data = json.load(f)
            objects = data.get("objects", [])
            diff = data.get("difficulty", {"CS": 4.0, "AR": 9.0, "OD": 8.0, "HP": 5.0, "SliderMultiplier": 1.4})
            sim_result = simulate_cursor_motion(objects, diff)
            sys.stdout.write(json.dumps(sim_result, indent=2) + "\n")
            sys.exit(0 if sim_result["playable"] else 1)

        else:
            parser.print_help(sys.stderr)
            sys.exit(2)

    except Exception as e:
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
