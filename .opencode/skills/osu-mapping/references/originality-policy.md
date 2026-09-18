# Originality Policy & Anti-Plagiarism Reference

This document defines the strict originality enforcement framework, similarity metrics, verdict classifications, and delivery blocking rules applied to all beatmaps generated or validated within the MultiAI Classroom workflow.

---

## 1. Core Principles

1. **Independent Creation**: Beatmaps must be original rhythmic and geometric compositions derived from the song's audio structure and style parameters.
2. **Plagiarism Prevention**: Direct copying of rhythm tracks, placement coordinates, or pattern sequences from community maps or mapper references is strictly prohibited.
3. **Auditability**: Every generated candidate is evaluated against known reference maps by the `osu_map_originality` tool, producing an objective similarity report.

---

## 2. Verdict Classifications

The originality engine evaluates the candidate beatmap against all provided references and assigns one of five definitive verdicts:

```
+---------------+----------------------------------------------------+---------------+
| Verdict       | Definition & Thresholds                            | Delivery Gate |
+---------------+----------------------------------------------------+---------------+
| ORIGINAL      | Full structural independence. No significant       | ALLOWED       |
|               | sequence matches; Rhythm Jaccard < 0.40.           | (PASS)        |
+---------------+----------------------------------------------------+---------------+
| DERIVATIVE    | Shares aggregate stylistic trends or section       | ALLOWED       |
|               | density, but rhythm timeline & geometry are unique.| (PASS w/ log) |
+---------------+----------------------------------------------------+---------------+
| NEAR_CLONE    | Contains >4 consecutive identical objects, or      | BLOCKED       |
|               | sequence match fraction 0.10 <= F_match < 0.30.    | (FAIL)        |
+---------------+----------------------------------------------------+---------------+
| CLONE         | Heavy direct copying or self-identical match.      | BLOCKED       |
|               | Sequence match fraction F_match >= 0.30.           | (FAIL)        |
+---------------+----------------------------------------------------+---------------+
| INCONCLUSIVE  | Reference set is empty, invalid, or unreadable     | BLOCKED       |
|               | when originality resolution was required.          | (NOT A PASS)  |
+---------------+----------------------------------------------------+---------------+
```

---

## 3. Anti-Plagiarism Hard Rules

### Rule 1: The 4-Object Sequence Limit
- **Rule**: Under no circumstances may a candidate beatmap contain a sequence of **more than 4 consecutive hit objects** that match a reference beatmap in both onset timestamp ($|\Delta t| < 5\text{ ms}$) and playfield position ($|\Delta x| \le 8\text{ px}, |\Delta y| \le 8\text{ px}$).
- **Violation Consequence**: Immediate classification as `NEAR_CLONE` or `CLONE`. Stage fails.

### Rule 2: Rhythm Foundation Independence
- **Rule**: Candidate rhythm timelines (the collection of active hit object onset times) must not be duplicated from a reference map.
- **Rhythm Jaccard Gate**:
  $$J_{\text{rhythm}}(C, R) = \frac{|T_C \cap T_R|}{|T_C \cup T_R|}$$
  - $J_{\text{rhythm}} \ge 0.70$ on songs with identical audio will trigger a `NEAR_CLONE` warning and require geometric dissimilarity proof.
  - $J_{\text{rhythm}} \ge 0.85$ combined with spatial similarity $> 0.50$ triggers `CLONE`.

### Rule 3: Self-Comparison Detection (Anti-Tampering)
- **Rule**: If a candidate beatmap is compared against itself or an identical duplicate, the similarity engine will detect $F_{\text{match}} = 1.0$ and assign `CLONE`. This prevents agents from passing validation by supplying the candidate as its own reference.

### Rule 4: `INCONCLUSIVE` is Never a Pass
- **Rule**: If `mapping-brief.json` specifies `require_originality_resolution: true`, an `INCONCLUSIVE` verdict is treated as a **hard failure**.
- The Teacher must not mark the run as `COMPLETE` when originality remains unresolved.

---

## 4. Similarity Metrics & Calculation Engine

The `osu_map_originality` tool computes four distinct metric dimensions:

### 4.1 Sequence Match Fraction ($F_{\text{match}}$)
Measures the proportion of candidate $n$-grams ($n = 4$) that appear in the reference beatmap:
$$F_{\text{match}} = \frac{\sum_{i=1}^{N - n + 1} \mathbb{I}(\text{CandidateSequence}_i \in \text{ReferenceSequences})}{N - n + 1}$$

- $F_{\text{match}} = 0.0$: Fully distinct patterns.
- $0.0 < F_{\text{match}} < 0.10$: Minor incidental common tropes (e.g. standard 1/2 kick slider on downbeat).
- $0.10 \le F_{\text{match}} < 0.30$: **NEAR_CLONE** boundary.
- $F_{\text{match}} \ge 0.30$: **CLONE** boundary.

---

### 4.2 Geometric Trajectory Correlation ($S_{\text{geo}}$)
For overlapping rhythm timestamps, compares displacement vectors:
$$\vec{v}_i = (x_{i+1} - x_i, y_{i+1} - y_i)$$
Cosine similarity of jump vectors across matching timestamps:
$$S_{\text{geo}} = \frac{1}{M} \sum_{k=1}^M \frac{\vec{v}_{C,k} \cdot \vec{v}_{R,k}}{\|\vec{v}_{C,k}\| \|\vec{v}_{R,k}\|}$$

---

### 4.3 Density & Spacing Profile Divergence
Compares moving window density (objects per second) and spacing distributions using Kullback-Leibler (KL) divergence. A `DERIVATIVE` map may have low KL divergence in density distribution while maintaining $F_{\text{match}} = 0.0$.

---

## 5. Originality Report Schema

The output generated by `osu_map_originality` is formatted as follows:

```json
{
  "$schema": "https://opencode.ai/schemas/originality-report.schema.json",
  "candidate_path": "C:/absolute/path/candidate.osu",
  "verdict": "ORIGINAL",
  "verdict_basis": "No n-gram sequences > 3 match reference. Rhythm Jaccard is 0.28.",
  "metrics": {
    "sequence_match_fraction": 0.0,
    "max_consecutive_matching_objects": 2,
    "rhythm_jaccard_similarity": 0.284,
    "geometric_trajectory_correlation": 0.121,
    "total_candidate_objects": 642,
    "total_reference_objects_analyzed": 1280
  },
  "comparisons": [
    {
      "reference_id": "ref_mapper_map_01.osu",
      "reference_checksum": "a1b2c3d4e5f6...",
      "matched_sequences_count": 0,
      "max_consecutive_match": 2,
      "rhythm_overlap_pct": 28.4
    }
  ],
  "passed": true
}
```

---

## 6. Remediation Guidelines

When an originality gate fails:
1. **If `CLONE` or `NEAR_CLONE`**:
   - Student Builder must re-run the Geometry and Rhythm generation passes with altered seed, varied jump angle profiles, or alternate rhythm anchor points.
2. **If `INCONCLUSIVE`**:
   - Student Architect must supply a valid reference `.osu` from the local workspace or community cache.
