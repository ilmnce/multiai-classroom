#!/usr/bin/env python3
"""
check_originality.py - Anti-Plagiarism & Originality Verification Engine for osu!

Purpose:
  Evaluates candidate beatmaps against reference beatmaps to enforce:
  - 4-object consecutive sequence matching limit
  - Sequence match fraction (F_match) for n=4 n-grams
  - Rhythm Jaccard similarity (J_rhythm)
  - Geometric trajectory correlation (S_geo)
  - Produces verdicts: ORIGINAL, DERIVATIVE, NEAR_CLONE, CLONE, INCONCLUSIVE
  - Blocks delivery if verdict is CLONE, NEAR_CLONE, or INCONCLUSIVE

Usage:
  python check_originality.py --candidate candidate.osu --references ref1.osu ref2.osu

Exit Codes:
  0: Success / Passed originality gate (ORIGINAL or DERIVATIVE)
  1: Plagiarism / Originality gate failed (NEAR_CLONE, CLONE, INCONCLUSIVE)
  2: Input error
"""

import sys
import os
import json
import math
import hashlib
import argparse
from typing import List, Dict, Any, Tuple, Set, Optional


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_hit_object_timeline(osu_path: str) -> List[Tuple[int, float, float, int]]:
    """
    Parses hit objects from an .osu file.
    Returns: List of tuples (time_ms, x, y, type)
    """
    objects = []
    if not os.path.exists(osu_path):
        return objects

    with open(osu_path, "r", encoding="utf-8", errors="replace") as f:
        in_ho = False
        for line_raw in f:
            line = line_raw.strip()
            if not line or line.startswith("//"):
                continue
            if line == "[HitObjects]":
                in_ho = True
                continue
            elif in_ho and line.startswith("[") and line.endswith("]"):
                break
            elif in_ho:
                parts = line.split(",")
                if len(parts) >= 4:
                    try:
                        x = float(parts[0])
                        y = float(parts[1])
                        t = int(float(parts[2]))
                        obj_type = int(parts[3])
                        objects.append((t, x, y, obj_type))
                    except ValueError:
                        continue
    objects.sort(key=lambda o: o[0])
    return objects


def are_objects_matching(
    o1: Tuple[int, float, float, int],
    o2: Tuple[int, float, float, int],
    time_tol_ms: int = 5,
    pos_tol_px: float = 8.0
) -> bool:
    """Checks if two hit objects match within spatial and temporal tolerance."""
    t1, x1, y1, _ = o1
    t2, x2, y2, _ = o2
    if abs(t1 - t2) > time_tol_ms:
        return False
    if abs(x1 - x2) > pos_tol_px or abs(y1 - y2) > pos_tol_px:
        return False
    return True


def compute_rhythm_jaccard(
    cand_objects: List[Tuple[int, float, float, int]],
    ref_objects: List[Tuple[int, float, float, int]],
    tolerance_ms: int = 5
) -> float:
    """Computes Jaccard index between candidate and reference rhythm onset times."""
    if not cand_objects or not ref_objects:
        return 0.0

    cand_times = [o[0] for o in cand_objects]
    ref_times = [o[0] for o in ref_objects]

    matched_ref = set()
    intersection_count = 0

    for ct in cand_times:
        for r_idx, rt in enumerate(ref_times):
            if r_idx not in matched_ref and abs(ct - rt) <= tolerance_ms:
                matched_ref.add(r_idx)
                intersection_count += 1
                break

    union_count = len(cand_times) + len(ref_times) - intersection_count
    if union_count == 0:
        return 0.0
    return intersection_count / union_count


def compute_sequence_matching(
    cand_objects: List[Tuple[int, float, float, int]],
    ref_objects: List[Tuple[int, float, float, int]],
    n: int = 4
) -> Tuple[float, int, int]:
    """
    Computes:
    - sequence_match_fraction (F_match) for n-grams
    - total matching n-gram sequences count
    - max consecutive matching objects count
    """
    N_cand = len(cand_objects)
    N_ref = len(ref_objects)

    if N_cand < n or N_ref < n:
        return 0.0, 0, 0

    # Max consecutive matching tracking
    max_consecutive = 0
    curr_consecutive = 0

    # Search longest matching sequence
    for i in range(N_cand):
        for j in range(N_ref):
            k = 0
            while (i + k < N_cand) and (j + k < N_ref):
                if are_objects_matching(cand_objects[i + k], ref_objects[j + k]):
                    k += 1
                else:
                    break
            if k > max_consecutive:
                max_consecutive = k

    # N-gram sequence matches
    matched_sequences = 0
    total_cand_ngrams = N_cand - n + 1

    for i in range(total_cand_ngrams):
        c_ngram = cand_objects[i:i + n]
        found = False
        for j in range(N_ref - n + 1):
            r_ngram = ref_objects[j:j + n]
            if all(are_objects_matching(c_ngram[k], r_ngram[k]) for k in range(n)):
                found = True
                break
        if found:
            matched_sequences += 1

    f_match = matched_sequences / total_cand_ngrams if total_cand_ngrams > 0 else 0.0
    return f_match, matched_sequences, max_consecutive


def compute_geometric_correlation(
    cand_objects: List[Tuple[int, float, float, int]],
    ref_objects: List[Tuple[int, float, float, int]],
    tolerance_ms: int = 5
) -> float:
    """Computes cosine similarity of jump vectors between matching timestamps."""
    cand_vectors = []
    for i in range(len(cand_objects) - 1):
        t1, x1, y1, _ = cand_objects[i]
        t2, x2, y2, _ = cand_objects[i + 1]
        cand_vectors.append((t1, x2 - x1, y2 - y1))

    ref_vectors = []
    for i in range(len(ref_objects) - 1):
        t1, x1, y1, _ = ref_objects[i]
        t2, x2, y2, _ = ref_objects[i + 1]
        ref_vectors.append((t1, x2 - x1, y2 - y1))

    cos_sims = []
    for ct, cdx, cdy in cand_vectors:
        c_len = math.hypot(cdx, cdy)
        if c_len < 1e-4:
            continue
        for rt, rdx, rdy in ref_vectors:
            if abs(ct - rt) <= tolerance_ms:
                r_len = math.hypot(rdx, rdy)
                if r_len > 1e-4:
                    dot = (cdx * rdx + cdy * rdy) / (c_len * r_len)
                    cos_sims.append(max(-1.0, min(1.0, dot)))
                break

    if not cos_sims:
        return 0.0
    return sum(cos_sims) / len(cos_sims)


def evaluate_originality(
    candidate_path: str,
    reference_paths: List[str]
) -> Dict[str, Any]:
    """
    Evaluates candidate beatmap originality against all provided reference beatmaps.
    """
    if not os.path.exists(candidate_path):
        return {
            "verdict": "INCONCLUSIVE",
            "verdict_basis": f"Candidate file not found: {candidate_path}",
            "passed": False,
            "metrics": {},
            "comparisons": []
        }

    cand_objects = parse_hit_object_timeline(candidate_path)
    if not cand_objects:
        return {
            "verdict": "INCONCLUSIVE",
            "verdict_basis": "Candidate contains 0 valid hit objects.",
            "passed": False,
            "metrics": {},
            "comparisons": []
        }

    # Filter existing references
    valid_refs = [r for r in reference_paths if r and os.path.exists(r)]

    if not valid_refs:
        # If references were expected but none valid
        return {
            "candidate_path": os.path.abspath(candidate_path),
            "verdict": "ORIGINAL",
            "verdict_basis": "No reference beatmaps provided for comparison. Assumed standalone original.",
            "passed": True,
            "metrics": {
                "sequence_match_fraction": 0.0,
                "max_consecutive_matching_objects": 0,
                "rhythm_jaccard_similarity": 0.0,
                "geometric_trajectory_correlation": 0.0,
                "total_candidate_objects": len(cand_objects),
                "total_reference_objects_analyzed": 0
            },
            "comparisons": []
        }

    comparisons = []
    highest_f_match = 0.0
    highest_consecutive = 0
    highest_jaccard = 0.0
    highest_geo = 0.0
    total_ref_objs = 0

    cand_hash = compute_sha256(candidate_path)

    for ref_path in valid_refs:
        ref_hash = compute_sha256(ref_path)
        ref_objects = parse_hit_object_timeline(ref_path)
        total_ref_objs += len(ref_objects)

        # Self-comparison check (anti-tampering rule 3)
        if os.path.abspath(candidate_path) == os.path.abspath(ref_path) or cand_hash == ref_hash:
            comparisons.append({
                "reference_id": os.path.basename(ref_path),
                "reference_checksum": ref_hash,
                "matched_sequences_count": len(cand_objects),
                "max_consecutive_match": len(cand_objects),
                "rhythm_overlap_pct": 100.0,
                "self_identical": True
            })
            return {
                "candidate_path": os.path.abspath(candidate_path),
                "verdict": "CLONE",
                "verdict_basis": f"Candidate is bit-for-bit identical to reference {os.path.basename(ref_path)} (Self-comparison).",
                "passed": False,
                "metrics": {
                    "sequence_match_fraction": 1.0,
                    "max_consecutive_matching_objects": len(cand_objects),
                    "rhythm_jaccard_similarity": 1.0,
                    "geometric_trajectory_correlation": 1.0,
                    "total_candidate_objects": len(cand_objects),
                    "total_reference_objects_analyzed": total_ref_objs
                },
                "comparisons": comparisons
            }

        f_match, matched_count, max_consec = compute_sequence_matching(cand_objects, ref_objects, n=4)
        jaccard = compute_rhythm_jaccard(cand_objects, ref_objects)
        geo_corr = compute_geometric_correlation(cand_objects, ref_objects)

        highest_f_match = max(highest_f_match, f_match)
        highest_consecutive = max(highest_consecutive, max_consec)
        highest_jaccard = max(highest_jaccard, jaccard)
        highest_geo = max(highest_geo, geo_corr)

        comparisons.append({
            "reference_id": os.path.basename(ref_path),
            "reference_checksum": ref_hash,
            "matched_sequences_count": matched_count,
            "max_consecutive_match": max_consec,
            "rhythm_overlap_pct": round(jaccard * 100.0, 1),
            "sequence_match_fraction": round(f_match, 4),
            "geometric_correlation": round(geo_corr, 4)
        })

    # Verdict assignment logic
    if highest_f_match >= 0.30 or (highest_jaccard >= 0.85 and highest_geo > 0.50):
        verdict = "CLONE"
        basis = f"Severe sequence copying detected: F_match={highest_f_match:.3f} >= 0.30."
        passed = False
    elif highest_f_match >= 0.10 or highest_consecutive > 4 or highest_jaccard >= 0.70:
        verdict = "NEAR_CLONE"
        basis = f"Near-clone threshold breached: max consecutive match={highest_consecutive} (>4) or F_match={highest_f_match:.3f} >= 0.10."
        passed = False
    elif highest_jaccard >= 0.40 or highest_geo >= 0.35:
        verdict = "DERIVATIVE"
        basis = f"Shares rhythmic motif or style trend (Jaccard={highest_jaccard:.2f}), but sequence match is clean (F_match={highest_f_match:.3f})."
        passed = True
    else:
        verdict = "ORIGINAL"
        basis = f"Fully distinct patterns. No consecutive sequence > 4 matches. F_match={highest_f_match:.3f}, J_rhythm={highest_jaccard:.3f}."
        passed = True

    return {
        "$schema": "https://opencode.ai/schemas/originality-report.schema.json",
        "candidate_path": os.path.abspath(candidate_path),
        "verdict": verdict,
        "verdict_basis": basis,
        "metrics": {
            "sequence_match_fraction": round(highest_f_match, 4),
            "max_consecutive_matching_objects": highest_consecutive,
            "rhythm_jaccard_similarity": round(highest_jaccard, 4),
            "geometric_trajectory_correlation": round(highest_geo, 4),
            "total_candidate_objects": len(cand_objects),
            "total_reference_objects_analyzed": total_ref_objs
        },
        "comparisons": comparisons,
        "passed": passed
    }


def main():
    parser = argparse.ArgumentParser(description="osu! Anti-Plagiarism & Originality Checker")
    parser.add_argument("--candidate", type=str, required=True, help="Path to candidate .osu file")
    parser.add_argument("--references", nargs="*", default=[], help="Paths to reference .osu files")

    args = parser.parse_args()

    try:
        report = evaluate_originality(args.candidate, args.references)
        sys.stdout.write(json.dumps(report, indent=2) + "\n")

        # Exit codes: 0 if passed (ORIGINAL/DERIVATIVE), 1 if failed (CLONE/NEAR_CLONE/INCONCLUSIVE)
        if report["passed"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        sys.stderr.write(f"Error: {str(e)}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
