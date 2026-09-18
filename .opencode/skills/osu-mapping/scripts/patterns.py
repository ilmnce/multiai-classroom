#!/usr/bin/env python3
"""
patterns.py - Geometric Pattern Catalog and Generator for osu! Standard

Purpose:
  Provides mathematical coordinate generators and pattern templates for osu!standard:
  - aimslop: Linear jumps, Triangle (3-point), Star (5-point), Perimeter jumps, Kick sliders
  - flow_aim: Curved streams, Spaced streams, Wave/S-curve sliders, Blanket sliders
  - hybrid: Multi-phase flow bursts resolving into sharp jump anchors
  - Geometry constraints: playfield margins [36, 476] x [36, 348], angle preservation, safe bounds

Usage:
  python patterns.py --style aimslop --pattern star_jumps --count 5
  python patterns.py --style flow_aim --pattern curved_stream --count 8

Exit Codes:
  0: Success
  2: Input error
"""

import sys
import json
import math
import argparse
from typing import List, Tuple, Dict, Any, Optional

# Playfield safe boundaries (with CS 4.0 margin padding)
MIN_X = 36
MAX_X = 476
MIN_Y = 36
MAX_Y = 348
CENTER_X = 256
CENTER_Y = 192


def clamp_coordinate(x: float, y: float, margin: int = 36) -> Tuple[int, int]:
    """Clamps (x, y) coordinates safely within playfield boundaries."""
    min_x = margin
    max_x = 512 - margin
    min_y = margin
    max_y = 384 - margin
    cx = max(min_x, min(max_x, round(x)))
    cy = max(min_y, min(max_y, round(y)))
    return cx, cy


def rotate_point(x: float, y: float, cx: float, cy: float, angle_rad: float) -> Tuple[float, float]:
    """Rotates point (x, y) around center (cx, cy) by angle_rad."""
    dx = x - cx
    dy = y - cy
    rx = dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
    ry = dx * math.sin(angle_rad) + dy * math.cos(angle_rad)
    return cx + rx, cy + ry


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


# -------------------------------------------------------------------------
# Aimslop Pattern Generators
# -------------------------------------------------------------------------

def generate_linear_jumps(
    start_pos: Tuple[int, int],
    count: int,
    jump_distance: float = 180.0,
    base_angle_rad: float = 0.5
) -> List[Tuple[int, int]]:
    """Generates back-and-forth or linear jump coordinates."""
    points: List[Tuple[int, int]] = [start_pos]
    curr_x, curr_y = start_pos
    angle = base_angle_rad

    for i in range(1, count):
        dx = math.cos(angle) * jump_distance
        dy = math.sin(angle) * jump_distance
        target_x = curr_x + dx
        target_y = curr_y + dy

        # Bounce if near wall
        if target_x < MIN_X or target_x > MAX_X:
            dx = -dx
            target_x = curr_x + dx
        if target_y < MIN_Y or target_y > MAX_Y:
            dy = -dy
            target_y = curr_y + dy

        cx, cy = clamp_coordinate(target_x, target_y)
        points.append((cx, cy))
        curr_x, curr_y = cx, cy
        # Flip angle for back-and-forth jump motion
        angle += math.pi + 0.35

    return points


def generate_triangle_jumps(
    center_pos: Tuple[int, int] = (CENTER_X, CENTER_Y),
    radius: float = 140.0,
    start_angle_rad: float = 0.0,
    count: int = 3
) -> List[Tuple[int, int]]:
    """Generates 3-point equilateral/isosceles triangle jump vertices."""
    points: List[Tuple[int, int]] = []
    step = 2.0 * math.pi / 3.0
    for i in range(count):
        a = start_angle_rad + (i * step)
        x = center_pos[0] + math.cos(a) * radius
        y = center_pos[1] + math.sin(a) * radius
        points.append(clamp_coordinate(x, y))
    return points


def generate_star_jumps(
    center_pos: Tuple[int, int] = (CENTER_X, CENTER_Y),
    radius: float = 160.0,
    start_angle_rad: float = -math.pi / 2.0,
    count: int = 5
) -> List[Tuple[int, int]]:
    """Generates 5-point star jump sequence crossing through center."""
    # 5 vertices ordered in star jump order (0 -> 2 -> 4 -> 1 -> 3)
    vertices = []
    step = 2.0 * math.pi / 5.0
    for i in range(5):
        a = start_angle_rad + (i * step)
        x = center_pos[0] + math.cos(a) * radius
        y = center_pos[1] + math.sin(a) * radius
        vertices.append(clamp_coordinate(x, y))

    star_order = [0, 2, 4, 1, 3]
    points = []
    for i in range(count):
        v_idx = star_order[i % 5]
        points.append(vertices[v_idx])
    return points


def generate_perimeter_jumps(count: int = 4) -> List[Tuple[int, int]]:
    """Generates wide cross-screen corner jumps."""
    corners = [
        (MIN_X + 20, MIN_Y + 20),
        (MAX_X - 20, MAX_Y - 20),
        (MIN_X + 20, MAX_Y - 20),
        (MAX_X - 20, MIN_Y + 20),
    ]
    points = []
    for i in range(count):
        points.append(corners[i % len(corners)])
    return points


# -------------------------------------------------------------------------
# Flow Aim Pattern Generators
# -------------------------------------------------------------------------

def generate_curved_stream(
    start_pos: Tuple[int, int],
    count: int,
    spacing: float = 28.0,
    start_angle_rad: float = 0.0,
    curve_rate_rad: float = 0.22
) -> List[Tuple[int, int]]:
    """Generates 1/4 note stream following smooth circular curvature."""
    points: List[Tuple[int, int]] = [start_pos]
    curr_x, curr_y = start_pos
    angle = start_angle_rad

    for i in range(1, count):
        angle += curve_rate_rad
        dx = math.cos(angle) * spacing
        dy = math.sin(angle) * spacing
        nx = curr_x + dx
        ny = curr_y + dy

        # Curve deflection if approaching screen edge
        if nx <= MIN_X + 10 or nx >= MAX_X - 10 or ny <= MIN_Y + 10 or ny >= MAX_Y - 10:
            angle += math.pi / 3.0  # Sharp turn inward
            dx = math.cos(angle) * spacing
            dy = math.sin(angle) * spacing
            nx = curr_x + dx
            ny = curr_y + dy

        cx, cy = clamp_coordinate(nx, ny)
        points.append((cx, cy))
        curr_x, curr_y = cx, cy

    return points


def generate_spaced_stream(
    start_pos: Tuple[int, int],
    count: int,
    spacing: float = 65.0,
    angle_rad: float = 0.4
) -> List[Tuple[int, int]]:
    """Generates spaced 1/4 stream requiring high aim precision and speed."""
    points: List[Tuple[int, int]] = [start_pos]
    curr_x, curr_y = start_pos

    for i in range(1, count):
        nx = curr_x + math.cos(angle_rad) * spacing
        ny = curr_y + math.sin(angle_rad) * spacing
        cx, cy = clamp_coordinate(nx, ny)
        points.append((cx, cy))
        curr_x, curr_y = cx, cy

    return points


def generate_wave_slider_points(
    start_pos: Tuple[int, int],
    end_pos: Tuple[int, int],
    amplitude: float = 40.0
) -> Tuple[str, float]:
    """
    Generates Bézier curve string (B|p1:p2|...) and estimated length for an S-curve/wave slider.
    """
    x1, y1 = start_pos
    x2, y2 = end_pos
    mid_x = (x1 + x2) / 2.0
    mid_y = (y1 + y2) / 2.0
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1e-4:
        dx, dy = 100.0, 0.0
        dist = 100.0

    # Normal vector perpendicular to trajectory
    norm_x = -dy / dist
    norm_y = dx / dist

    # Control point 1 (1/3 along, shifted positive normal)
    cp1_x, cp1_y = clamp_coordinate(x1 + dx * 0.33 + norm_x * amplitude, y1 + dy * 0.33 + norm_y * amplitude)
    # Control point 2 (2/3 along, shifted negative normal)
    cp2_x, cp2_y = clamp_coordinate(x1 + dx * 0.67 - norm_x * amplitude, y1 + dy * 0.67 - norm_y * amplitude)
    end_cx, end_cy = clamp_coordinate(x2, y2)

    curve_spec = f"B|{cp1_x}:{cp1_y}|{cp2_x}:{cp2_y}|{end_cx}:{end_cy}"
    approx_len = dist * 1.15
    return curve_spec, approx_len


def generate_blanket_slider_points(
    circle_pos: Tuple[int, int],
    radius: float = 90.0,
    start_angle: float = 0.0,
    arc_span: float = math.pi
) -> Tuple[Tuple[int, int], str, float]:
    """
    Generates a Perfect Circle (P) slider wrapped around a central hit circle (blanketing).
    Returns: (slider_start_pos, curve_string, length)
    """
    cx, cy = circle_pos
    mid_angle = start_angle + (arc_span / 2.0)
    end_angle = start_angle + arc_span

    p0_x, p0_y = clamp_coordinate(cx + math.cos(start_angle) * radius, cy + math.sin(start_angle) * radius)
    p1_x, p1_y = clamp_coordinate(cx + math.cos(mid_angle) * radius, cy + math.sin(mid_angle) * radius)
    p2_x, p2_y = clamp_coordinate(cx + math.cos(end_angle) * radius, cy + math.sin(end_angle) * radius)

    curve_spec = f"P|{p1_x}:{p1_y}|{p2_x}:{p2_y}"
    length = abs(radius * arc_span)
    return (p0_x, p0_y), curve_spec, length


def generate_kick_slider_points(
    start_pos: Tuple[int, int],
    angle_rad: float = 0.0,
    length: float = 85.0
) -> Tuple[str, float]:
    """Generates a fast Linear (L) kick slider."""
    x1, y1 = start_pos
    x2, y2 = clamp_coordinate(x1 + math.cos(angle_rad) * length, y1 + math.sin(angle_rad) * length)
    curve_spec = f"L|{x2}:{y2}"
    actual_len = distance(start_pos, (x2, y2))
    return curve_spec, actual_len


# -------------------------------------------------------------------------
# Formatting Utilities
# -------------------------------------------------------------------------

def format_hit_circle(x: int, y: int, time_ms: int, new_combo: bool = False, hitsound: int = 0) -> str:
    """Formats an osu! hit circle object line."""
    obj_type = 5 if new_combo else 1
    return f"{x},{y},{time_ms},{obj_type},{hitsound},0:0:0:0:"


def format_slider(
    x: int,
    y: int,
    time_ms: int,
    curve_spec: str,
    slides: int = 1,
    length: float = 120.0,
    new_combo: bool = False,
    hitsound: int = 0
) -> str:
    """Formats an osu! slider object line."""
    obj_type = 6 if new_combo else 2
    # Build default edge hitsounds and edge sets
    edge_sounds = "|".join([str(hitsound)] * (slides + 1))
    edge_sets = "|".join(["0:0"] * (slides + 1))
    return f"{x},{y},{time_ms},{obj_type},{hitsound},{curve_spec},{slides},{length:.2f},{edge_sounds},{edge_sets},0:0:0:0:"


def format_spinner(time_ms: int, end_time_ms: int, new_combo: bool = True, hitsound: int = 0) -> str:
    """Formats an osu! spinner object line."""
    obj_type = 12 if new_combo else 8
    return f"256,192,{time_ms},{obj_type},{hitsound},{end_time_ms},0:0:0:0:"


def main():
    parser = argparse.ArgumentParser(description="osu! Pattern Generator")
    parser.add_argument("--style", type=str, default="aimslop", choices=["aimslop", "flow_aim", "hybrid"])
    parser.add_argument("--pattern", type=str, default="star_jumps")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--start-x", type=int, default=CENTER_X)
    parser.add_argument("--start-y", type=int, default=CENTER_Y)

    args = parser.parse_args()

    start = (args.start_x, args.start_y)
    pattern_name = args.pattern.lower()

    points = []
    if pattern_name == "star_jumps":
        points = generate_star_jumps(start, count=args.count)
    elif pattern_name == "triangle_jumps":
        points = generate_triangle_jumps(start, count=args.count)
    elif pattern_name == "linear_jumps":
        points = generate_linear_jumps(start, count=args.count)
    elif pattern_name == "curved_stream":
        points = generate_curved_stream(start, count=args.count)
    elif pattern_name == "spaced_stream":
        points = generate_spaced_stream(start, count=args.count)
    elif pattern_name == "perimeter_jumps":
        points = generate_perimeter_jumps(count=args.count)
    else:
        sys.stderr.write(f"Unknown pattern: {pattern_name}\n")
        sys.exit(2)

    output = {
        "style": args.style,
        "pattern": pattern_name,
        "count": len(points),
        "points": points
    }
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
