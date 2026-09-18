#!/usr/bin/env python3
"""
section_planner.py - Section Planning & Structural Dynamics for osu! Mapping

Purpose:
  Divides song timeline into structured musical sections (Intro, Verse, Pre-Chorus,
  Chorus/Kiai, Bridge, Outro) and assigns intensity, rhythm density multipliers,
  spacing multipliers, and recommended pattern templates according to the mapping style.

Usage:
  python section_planner.py --duration 180000 --bpm 180 --offset 1250 --style flow_aim
  python section_planner.py --plan mapping-plan.json

Exit Codes:
  0: Success
  2: Input error
"""

import sys
import json
import argparse
from typing import List, Dict, Any, Optional


def plan_sections(
    duration_ms: int,
    bpm: float,
    offset_ms: int,
    style: str = "hybrid",
    meter: int = 4
) -> List[Dict[str, Any]]:
    """
    Generates structured song sections with intensity and style-based pattern profiles.
    """
    if duration_ms <= 0 or bpm <= 0:
        raise ValueError(f"Invalid duration ({duration_ms}) or BPM ({bpm})")

    beat_len = 60000.0 / bpm
    measure_len = beat_len * meter

    # Calculate total measures available
    effective_duration = duration_ms - offset_ms
    total_measures = max(4, int(effective_duration / measure_len))

    # Standard section allocation proportions
    # Layout depends on total duration
    if total_measures < 16:
        # Very short track / TV size clip
        sections_spec = [
            ("Intro", 0.15, 0.4, False, 0.8),
            ("Verse", 0.35, 0.6, False, 1.0),
            ("Chorus", 0.40, 1.0, True, 1.3),
            ("Outro", 0.10, 0.3, False, 0.7),
        ]
    elif total_measures < 40:
        # TV size (~90s)
        sections_spec = [
            ("Intro", 0.10, 0.35, False, 0.75),
            ("Verse", 0.25, 0.55, False, 0.95),
            ("Pre-Chorus", 0.15, 0.75, False, 1.1),
            ("Chorus", 0.35, 1.0, True, 1.35),
            ("Outro", 0.15, 0.35, False, 0.7),
        ]
    else:
        # Full length song (>2 mins)
        sections_spec = [
            ("Intro", 0.08, 0.35, False, 0.7),
            ("Verse 1", 0.18, 0.5, False, 0.9),
            ("Pre-Chorus 1", 0.10, 0.7, False, 1.05),
            ("Chorus 1", 0.20, 1.0, True, 1.3),
            ("Verse 2", 0.14, 0.55, False, 0.95),
            ("Bridge", 0.10, 0.4, False, 0.8),
            ("Chorus 2", 0.15, 1.0, True, 1.4),
            ("Outro", 0.05, 0.3, False, 0.65),
        ]

    # Pattern catalog suggestions based on style and intensity
    style_clean = style.lower()

    sections: List[Dict[str, Any]] = []
    current_time = offset_ms

    for idx, (name, prop, intensity, kiai, spacing_mult) in enumerate(sections_spec):
        section_measures = max(2, round(total_measures * prop))
        sec_duration = int(section_measures * measure_len)
        sec_end = min(duration_ms, int(current_time + sec_duration))

        # Adjust last section to cover up to duration_ms
        if idx == len(sections_spec) - 1:
            sec_end = duration_ms

        # Pattern suggestions based on style
        if style_clean == "aimslop":
            if kiai:
                patterns = ["star_jumps", "triangle_jumps", "perimeter_jumps", "kick_sliders"]
                density = 1.0
            elif intensity > 0.6:
                patterns = ["linear_jumps", "triangle_jumps", "kick_sliders"]
                density = 0.85
            else:
                patterns = ["slow_jumps", "simple_sliders", "triplet_burst"]
                density = 0.65
        elif style_clean == "flow_aim":
            if kiai:
                patterns = ["curved_stream", "spaced_stream", "wave_slider", "blanket_slider"]
                density = 0.95
            elif intensity > 0.6:
                patterns = ["curved_stream", "wave_slider", "blanket_slider"]
                density = 0.8
            else:
                patterns = ["gentle_curved_slider", "blanket_slider", "triplet_burst"]
                density = 0.6
        else:  # hybrid
            if kiai:
                patterns = ["star_jumps", "spaced_stream", "wave_slider", "kick_sliders"]
                density = 1.0
            elif intensity > 0.6:
                patterns = ["curved_stream", "linear_jumps", "wave_slider"]
                density = 0.85
            else:
                patterns = ["gentle_curved_slider", "blanket_slider", "triplet_burst"]
                density = 0.6

        sections.append({
            "section_index": idx + 1,
            "name": name,
            "start_time_ms": int(current_time),
            "end_time_ms": int(sec_end),
            "duration_ms": int(sec_end - current_time),
            "intensity": round(intensity, 2),
            "kiai": kiai,
            "density_factor": round(density, 2),
            "spacing_multiplier": round(spacing_mult, 2),
            "slider_velocity_multiplier": 1.2 if kiai else 1.0,
            "recommended_patterns": patterns
        })

        current_time = sec_end
        if current_time >= duration_ms:
            break

    return sections


def main():
    parser = argparse.ArgumentParser(description="osu! Section Planner")
    parser.add_argument("--duration", type=int, default=120000, help="Total audio duration in ms")
    parser.add_argument("--bpm", type=float, default=180.0, help="BPM")
    parser.add_argument("--offset", type=int, default=1000, help="Offset in ms")
    parser.add_argument("--style", type=str, default="hybrid", choices=["aimslop", "flow_aim", "hybrid"], help="Mapping style")
    parser.add_argument("--plan", type=str, help="Optional path to mapping-plan.json to read inputs")

    args = parser.parse_args()

    try:
        duration = args.duration
        bpm = args.bpm
        offset = args.offset
        style = args.style

        if args.plan:
            with open(args.plan, "r", encoding="utf-8") as f:
                plan_data = json.load(f)
            norm = plan_data.get("normalized_input") or plan_data.get("input_normalized") or {}
            bpm = norm.get("bpm", bpm)
            offset = norm.get("offset_ms", offset)
            style = norm.get("style", style)
            # Check facts for duration if available
            facts = plan_data.get("facts") or []
            for fact in facts:
                if "duration is" in fact.lower() and "ms" in fact.lower():
                    try:
                        part = fact.lower().split("duration is")[1].split("ms")[0].strip()
                        duration = int(float(part))
                    except Exception:
                        pass

        sections = plan_sections(duration_ms=duration, bpm=bpm, offset_ms=offset, style=style)
        output = {
            "duration_ms": duration,
            "bpm": bpm,
            "offset_ms": offset,
            "style": style,
            "total_sections": len(sections),
            "sections": sections
        }
        sys.stdout.write(json.dumps(output, indent=2) + "\n")
        sys.exit(0)

    except Exception as e:
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
