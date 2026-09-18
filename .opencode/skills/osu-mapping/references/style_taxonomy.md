# osu! Mapping Style Taxonomy & Pattern Catalog

This reference defines the taxonomy of mapping styles, structural design parameters, target difficulty bands, and pattern catalogs used by the `osu-mapping` generator and validator.

---

## 1. Style Classification

```
                           +---------------------------+
                           |   Mapping Style Profiles  |
                           +---------------------------+
                                         |
            +----------------------------+----------------------------+
            |                            |                            |
            v                            v                            v
     [ aimslop ]                   [ flow_aim ]                  [ hybrid ]
  * Sharp jump angles           * Smooth curvature           * Sectional dynamics
  * High cross-screen velocity  * Continuous circular flow   * Verse: flow/sliders
  * Snap-heavy 1/2 rhythm       * Streams & slider blankets  * Chorus: jump spikes
  * High aim star rating        * Finger-control emphasis    * Adaptive transitions
```

### 1.1 `aimslop`
- **Philosophy**: Maximizes cursor velocity and snap agility through wide-angle cross-screen jumps, sharp directional changes, and high spacing multipliers.
- **Rhythm Characteristics**:
  - Predominantly 1/2 beat jump sequences with high rhythmic density.
  - Minimal sustained streams; bursts are limited to 3-5 notes (triplets/quintets) acting as jump transitions.
  - Short, functional sliders (1/2 or 1/4 kick sliders) used primarily as velocity resets or emphasis anchors.
- **Geometric Characteristics**:
  - **Sharp / Acute Angles**: Jump sequences frequently use 60° to 120° angles to create snapping hand motions.
  - **Polygon Structures**: Triangles (3-point jumps), stars (5-point jumps), boxes, and cross-screen jumps spanning $>250$ osupixels.
  - **Boundary Utilization**: Heavy usage of outer playfield edges to maximize jump distance.
- **Typical Settings**:
  - AR: `9.2 - 9.8`
  - CS: `4.0 - 4.4` (smaller targets demand precise snaps)
  - OD: `8.5 - 9.5`
  - SV: `1.4 - 1.8` (fast base slider speed)

---

### 1.2 `flow_aim`
- **Philosophy**: Emphasizes aesthetic curvature, visual harmony, momentum preservation, and rotational flow across the playfield.
- **Rhythm Characteristics**:
  - Balanced distribution between 1/4 streams, 1/2 sliders, and melodic rhythmic pauses.
  - Extensive use of continuous 1/4 streams (7 to 17+ notes) and complex rhythmic finger control.
  - Long, expressive sliders with varying slider velocities (SV changes via inherited timing points).
- **Geometric Characteristics**:
  - **Smooth / Obtuse Angles**: Object trajectories preserve angular momentum (>120° to 160° smooth sweeps).
  - **Circular Flow**: Clockwise and counter-clockwise orbital movement across the screen.
  - **Blanketing**: Sliders curved precisely to wrap around preceding or subsequent hit circles at uniform spacing.
  - **Wave & Spline Sliders**: Multi-anchor Bézier curves and gentle S-curves.
- **Typical Settings**:
  - AR: `9.0 - 9.5`
  - CS: `3.8 - 4.2`
  - OD: `8.5 - 9.2`
  - SV: `1.2 - 1.6`

---

### 1.3 `hybrid`
- **Philosophy**: Combines the expressive fluidity of `flow_aim` during atmospheric, verse, and build-up sections with the explosive intensity and sharp snap jumps of `aimslop` during kiai/chorus climaxes.
- **Rhythm & Geometry**:
  - Dynamic density scaling matching song intensity (intro/outro: moderate spacing; verse: flow/sliders; chorus: large jumps and spaced bursts).
  - Employs anti-flow reversals at major musical downbeats or finish hitsounds.
- **Typical Settings**:
  - AR: `9.2 - 9.6`
  - CS: `4.0 - 4.2`
  - OD: `8.8 - 9.4`
  - SV: `1.3 - 1.7`

---

## 2. Target Star Rating Bands

When planning beatmap generation, the Architect sets difficulty parameters to target specific Star Rating (SR) bands:

| Difficulty Name | Star Range | Key Rhythm Densities | Spacing Multiplier | Typical AR / CS / OD |
|---|---|---|---|---|
| **Easy** | `1.50 - 2.29*` | 1/1, 2/1 notes, simple 1/1 sliders | Fixed Distance Snap (0.8x - 1.0x) | AR 3 - 5 / CS 3.0 - 3.5 / OD 3 - 4 |
| **Normal** | `2.30 - 3.29*` | 1/1 and 1/2 notes, 1/2 sliders | Fixed Distance Snap (1.0x - 1.2x) | AR 5 - 7 / CS 3.5 - 4.0 / OD 5 - 6 |
| **Hard** | `3.30 - 4.29*` | 1/2 jumps, basic 1/4 bursts (3-5 notes) | Moderate (1.2x - 1.5x) | AR 7.5 - 8.5 / CS 3.8 - 4.0 / OD 7 - 8 |
| **Insane** | `4.30 - 5.29*` | 1/2 jumps, active 1/4 streams, kick sliders | High (1.5x - 2.0x) | AR 8.8 - 9.3 / CS 4.0 - 4.2 / OD 8.2 - 9.0 |
| **Expert** | `5.30 - 6.29*` | Spaced 1/4 streams, wide cross-screen jumps | Dynamic (1.8x - 2.5x) | AR 9.2 - 9.6 / CS 4.0 - 4.5 / OD 9.0 - 9.5 |
| **Extra / Master**| `6.30+*` | Extreme spacing spikes, fast streams, complex snaps | Extreme (> 2.5x) | AR 9.5 - 10.0 / CS 4.2 - 5.0 / OD 9.2 - 10.0 |

---

## 3. Pattern Catalog Reference

```
  [ Jump Patterns ]             [ Stream Patterns ]           [ Slider Patterns ]
  - Linear Jump                 - Straight Stream             - Blanket Slider
  - Triangle (3-point)          - Curved Stream               - Wave (S-Curve)
  - Star (5-point)              - Spaced Stream               - Kick Slider (1/4 rev)
  - Box / Square                - Cut Stream (doubles)        - Red-anchor Hinge
```

### 3.1 Jump Patterns
1. **Linear Jump**: Alternating objects along a straight vector. Spacing must remain consistent or linearly accelerate.
2. **Triangle Jump**: 3-object pattern forming an equilateral or isosceles triangle. Angles typically 60° (sharp snap).
3. **Star Jump**: 5-object cycle crisscrossing a central focus point, creating wide snapping momentum.
4. **Perimeter / Screen-Wrap Jump**: Jumps tracing outer quadrant coordinates `(x1, y1) -> (x2, y2)` across opposing corners.

### 3.2 Stream Patterns
1. **Curved Stream**: 1/4 note stream following a continuous Bézier or circular arc. Spacing should remain uniform (0.3x - 0.6x distance multiplier).
2. **Spaced Stream**: 1/4 stream with increased spacing (>1.0x distance multiplier), requiring both high aim velocity and tapping accuracy.
3. **Accelerating Stream**: Gradual spacing expansion from low spacing to high spacing reflecting crescendo in the music.
4. **Stream with Angle Inversion (Snake Stream)**: S-shaped stream reversing rotational direction on a prominent percussion hit.

### 3.3 Slider Patterns
1. **Blanket**: A curved slider whose arc center matches the position of a subsequent or preceding hit circle, maintaining equal visual radius.
2. **Wave / S-Curve Slider**: Bézier slider with 4 control points producing symmetric undulating curves.
3. **Red-Anchor Hinge Slider**: Bézier slider with duplicate control points at the hinge (`x:y|x:y`), creating sharp V-shapes or lightning bolts.
4. **Kick Slider**: Fast 1/4 or 1/8 reverse slider providing heavy tactile feedback on high-energy vocal or synthesizer pulses.

### 3.4 Stacks and Bursts
1. **Triplet Burst**: Exactly 3 notes snapped to 1/4 divisor, stacked or slightly spaced, resolving into a slider head.
2. **Quintet Burst**: 5 notes on 1/4 divisor leading into a downbeat.
3. **Overlap Stack**: Hit objects sharing identical `(x, y)` coordinates within the stack leniency window for visual clarity.
