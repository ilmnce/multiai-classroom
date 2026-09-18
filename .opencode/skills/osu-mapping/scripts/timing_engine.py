#!/usr/bin/env python3
"""
timing_engine.py - Beat Grid and Timing Engine for osu! Standard

Purpose:
  Parses osu! timing points, computes active BPM and Slider Velocity (SV),
  evaluates beat-grid snapping against standard divisors (1/1, 1/2, 1/3, 1/4, 1/6, 1/8),
  and generates timing grids for beatmap generation passes.

Usage:
  python timing_engine.py --file candidate.osu
  python timing_engine.py --check-snap --time 12500 --bpm 180 --offset 1250
  python timing_engine.py --grid --bpm 180 --offset 1250 --start 1250 --end 60000

Exit Codes:
  0: Success / Valid timing
  1: Timing validation failure (unsnapped objects, invalid point order)
  2: Input error (missing file, bad arguments)
"""

import sys
import json
import argparse
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class TimingPoint:
    time: int
    beat_length: float
    meter: int = 4
    sample_set: int = 0
    sample_index: int = 0
    volume: int = 100
    uninherited: bool = True
    effects: int = 0

    @property
    def is_red(self) -> bool:
        """True if uninherited (BPM/offset anchor)."""
        return self.uninherited

    @property
    def is_green(self) -> bool:
        """True if inherited (SV/volume anchor)."""
        return not self.uninherited

    @property
    def bpm(self) -> float:
        """Computes BPM for uninherited timing points."""
        if self.uninherited and self.beat_length > 0:
            return 60000.0 / self.beat_length
        return 0.0

    @property
    def sv_multiplier(self) -> float:
        """Computes Slider Velocity multiplier for inherited points."""
        if not self.uninherited:
            if self.beat_length < 0:
                return max(0.1, min(10.0, -100.0 / self.beat_length))
            return 1.0
        return 1.0

    def to_osu_line(self) -> str:
        uninh_val = 1 if self.uninherited else 0
        return f"{self.time},{self.beat_length:.6f},{self.meter},{self.sample_set},{self.sample_index},{self.volume},{uninh_val},{self.effects}"


def parse_timing_points_section(section_lines: List[str]) -> List[TimingPoint]:
    """Parses raw lines from [TimingPoints] section."""
    points: List[TimingPoint] = []
    for line_raw in section_lines:
        line = line_raw.strip()
        if not line or line.startswith("//"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            time_val = int(float(parts[0]))
            beat_len = float(parts[1])
            meter = int(parts[2]) if len(parts) > 2 else 4
            sample_set = int(parts[3]) if len(parts) > 3 else 0
            sample_index = int(parts[4]) if len(parts) > 4 else 0
            volume = int(parts[5]) if len(parts) > 5 else 100
            uninherited = bool(int(parts[6])) if len(parts) > 6 else True
            effects = int(parts[7]) if len(parts) > 7 else 0
            points.append(TimingPoint(
                time=time_val,
                beat_length=beat_len,
                meter=meter,
                sample_set=sample_set,
                sample_index=sample_index,
                volume=volume,
                uninherited=uninherited,
                effects=effects
            ))
        except (ValueError, IndexError):
            continue
    points.sort(key=lambda p: (p.time, not p.uninherited))
    return points


def get_active_uninherited_point(time_ms: int, timing_points: List[TimingPoint]) -> Optional[TimingPoint]:
    """Returns the effective uninherited (Red) timing point at given time."""
    active: Optional[TimingPoint] = None
    for p in timing_points:
        if p.uninherited:
            if p.time <= time_ms or active is None:
                active = p
            else:
                break
    return active


def get_active_sv(time_ms: int, timing_points: List[TimingPoint]) -> float:
    """Computes active Slider Velocity multiplier at given timestamp."""
    sv = 1.0
    for p in timing_points:
        if p.time <= time_ms:
            if not p.uninherited:
                sv = p.sv_multiplier
            else:
                sv = 1.0  # Reset to 1.0 on uninherited point unless followed by inherited point at same time
        else:
            break
    return sv


def is_snapped(
    time_ms: int,
    uninherited_points: List[TimingPoint],
    allowed_divisors: Tuple[int, ...] = (1, 2, 3, 4, 6, 8, 12, 16),
    tolerance_ms: float = 3.0
) -> Tuple[bool, Optional[int], float]:
    """
    Checks if a timestamp is snapped to a valid divisor on the beat grid.
    Returns: (is_snapped, best_divisor, diff_ms)
    """
    if not uninherited_points:
        return False, None, float("inf")

    # Find the applicable uninherited point
    point = get_active_uninherited_point(time_ms, uninherited_points)
    if not point or point.beat_length <= 0:
        return False, None, float("inf")

    beat_len = point.beat_length
    offset = point.time
    dt = time_ms - offset

    best_divisor = None
    min_diff = float("inf")

    for div in allowed_divisors:
        interval = beat_len / div
        beats_f = dt / interval
        nearest_step = round(beats_f)
        diff = abs(dt - (nearest_step * interval))
        if diff < min_diff:
            min_diff = diff
            best_divisor = div
        if diff <= tolerance_ms:
            return True, div, diff

    return (min_diff <= tolerance_ms), best_divisor, min_diff


def generate_beat_grid(
    start_ms: int,
    end_ms: int,
    bpm: float,
    offset_ms: int,
    divisors: Tuple[int, ...] = (1, 2, 4)
) -> List[Dict[str, Any]]:
    """Generates beat grid timestamps between start_ms and end_ms."""
    if bpm <= 0:
        raise ValueError(f"Invalid BPM: {bpm}")
    beat_len = 60000.0 / bpm
    grid_points: List[Dict[str, Any]] = []

    # Smallest interval from max divisor
    max_div = max(divisors)
    step_ms = beat_len / max_div

    # Find first step >= start_ms
    start_step = int((start_ms - offset_ms) / step_ms)
    if offset_ms + (start_step * step_ms) < start_ms:
        start_step += 1

    curr_step = start_step
    while True:
        t = round(offset_ms + (curr_step * step_ms))
        if t > end_ms:
            break
        # Determine divisor class (1/1, 1/2, 1/4, etc.)
        matched_div = max_div
        for d in sorted(divisors):
            div_step = max_div // d
            if curr_step % div_step == 0:
                matched_div = d
                break

        grid_points.append({
            "time_ms": t,
            "divisor": matched_div,
            "is_downbeat": (curr_step % (max_div * 4) == 0)
        })
        curr_step += 1

    return grid_points


def main():
    parser = argparse.ArgumentParser(description="osu! Beat Grid & Timing Engine")
    parser.add_argument("--file", type=str, help="Path to .osu beatmap file to parse timing")
    parser.add_argument("--check-snap", action="store_true", help="Check snap of timestamp")
    parser.add_argument("--time", type=int, help="Timestamp in ms to test")
    parser.add_argument("--bpm", type=float, help="BPM value")
    parser.add_argument("--offset", type=int, default=0, help="Offset in ms")
    parser.add_argument("--grid", action="store_true", help="Generate beat grid")
    parser.add_argument("--start", type=int, default=0, help="Start time in ms for grid")
    parser.add_argument("--end", type=int, default=60000, help="End time in ms for grid")

    args = parser.parse_args()

    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            in_tp = False
            tp_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped == "[TimingPoints]":
                    in_tp = True
                    continue
                elif in_tp and stripped.startswith("[") and stripped.endswith("]"):
                    break
                elif in_tp:
                    tp_lines.append(stripped)

            points = parse_timing_points_section(tp_lines)
            red_points = [p for p in points if p.uninherited]
            green_points = [p for p in points if not p.uninherited]

            output = {
                "file": args.file,
                "total_timing_points": len(points),
                "uninherited_count": len(red_points),
                "inherited_count": len(green_points),
                "primary_bpm": red_points[0].bpm if red_points else None,
                "primary_offset_ms": red_points[0].time if red_points else None,
                "timing_points": [
                    {
                        "time": p.time,
                        "uninherited": p.uninherited,
                        "bpm": p.bpm if p.uninherited else None,
                        "sv_multiplier": p.sv_multiplier if not p.uninherited else None,
                        "meter": p.meter,
                        "volume": p.volume
                    }
                    for p in points
                ]
            }
            sys.stdout.write(json.dumps(output, indent=2) + "\n")
            sys.exit(0)

        elif args.check_snap:
            if args.time is None or not args.bpm:
                sys.stderr.write("Error: --time and --bpm are required for --check-snap\n")
                sys.exit(2)
            ref_point = TimingPoint(time=args.offset, beat_length=60000.0 / args.bpm, uninherited=True)
            snapped, div, diff = is_snapped(args.time, [ref_point])
            result = {
                "time_ms": args.time,
                "bpm": args.bpm,
                "offset_ms": args.offset,
                "is_snapped": snapped,
                "best_divisor": div,
                "difference_ms": round(diff, 3)
            }
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
            sys.exit(0 if snapped else 1)

        elif args.grid:
            if not args.bpm:
                sys.stderr.write("Error: --bpm is required for --grid\n")
                sys.exit(2)
            grid = generate_beat_grid(args.start, args.end, args.bpm, args.offset)
            sys.stdout.write(json.dumps({"count": len(grid), "ticks": grid}, indent=2) + "\n")
            sys.exit(0)

        else:
            parser.print_help(sys.stderr)
            sys.exit(2)

    except Exception as e:
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
