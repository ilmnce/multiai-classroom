# osu! File Format Reference (`.osu` v14)

This reference defines the structure, syntax, timing semantics, and mathematical formulas of the `.osu` file format (v14) for osu!standard (`Mode: 0`).

---

## 1. File Structure Overview

An `.osu` file is a plain text file encoded in UTF-8. It begins with a format version declaration header, followed by categorized sections marked by square brackets `[...]`.

```text
osu file format v14

[General]
...
[Editor]
...
[Metadata]
...
[Difficulty]
...
[Events]
...
[TimingPoints]
...
[Colours]
...
[HitObjects]
...
```

---

## 2. Section Specifications

### 2.1 `[General]`
Contains general audio and game mode properties. Key-value pairs are separated by a colon (`:`).

| Key | Type | Description | Default / Valid |
|---|---|---|---|
| `AudioFilename` | String | Relative filename of the audio track in the beatmap folder | e.g. `audio.mp3` |
| `AudioLeadIn` | Integer | Milliseconds of silence added before audio starts | `0` |
| `PreviewTime` | Integer | Audio timestamp in milliseconds where song preview starts in song select | `-1` (default) or ms |
| `Countdown` | Integer | Countdown speed before first object: `0` = None, `1` = Normal, `2` = Half, `3` = Double | `0` |
| `SampleSet` | String | Default sample set: `Normal`, `Soft`, or `Drum` | `Soft` |
| `StackLeniency` | Float | Multiplier for hit object stacking leniency | `0.0` to `1.0` (typically `0.7`) |
| `Mode` | Integer | Game mode: `0` = osu!standard, `1` = Taiko, `2` = Catch, `3` = Mania | **Must be `0` for osu!standard** |
| `LetterboxInBreaks` | Integer | Letterbox display during break periods (`0` = No, `1` = Yes) | `0` |
| `WidescreenStoryboard` | Integer | Storyboard widescreen support 16:9 (`0` = 4:3, `1` = 16:9) | `1` |

---

### 2.2 `[Editor]`
Stores editor state configuration. Does not affect gameplay.

| Key | Type | Description |
|---|---|---|
| `Bookmarks` | Comma-separated Integers | Array of millisecond timestamps for bookmarks |
| `DistanceSpacing` | Float | Visual spacing multiplier in the editor |
| `BeatDivisor` | Integer | Selected beat snap divisor (e.g. `4` for 1/4, `3` for 1/3, `8` for 1/8) |
| `GridSize` | Integer | Editor grid snap size (e.g. `4`, `8`, `16`, `32`) |
| `TimelineZoom` | Float | Zoom scale of the timeline |

---

### 2.3 `[Metadata]`
Information about the song, artist, creator, and difficulty version.

| Key | Type | Description |
|---|---|---|
| `Title` | String | Romanised title of the song |
| `TitleUnicode` | String | Native/Unicode title of the song |
| `Artist` | String | Romanised artist name |
| `ArtistUnicode` | String | Native/Unicode artist name |
| `Creator` | String | Username of the beatmap creator |
| `Version` | String | Difficulty name (e.g. `Hard`, `Insane`, `Extra`) |
| `Source` | String | Origin of the song (e.g. Anime, Game, Album) |
| `Tags` | Space-separated Strings | Search terms separated by single spaces |
| `BeatmapID` | Integer | Online ID of the beatmap (`0` for local unsubmitted) |
| `BeatmapSetID` | Integer | Online ID of the beatmap set (`-1` or `0` for unsubmitted) |

---

### 2.4 `[Difficulty]`
Defines difficulty parameters affecting hit window sizes, speed, and drain.

| Key | Type | Range | Description |
|---|---|---|---|
| `HPDrainRate` (HP) | Float | `0.0 - 10.0` | Health drain rate and recovery difficulty |
| `CircleSize` (CS) | Float | `0.0 - 10.0` | Hit circle radius size (higher = smaller circles) |
| `OverallDifficulty` (OD) | Float | `0.0 - 10.0` | Hit window accuracy strictness (300/100/50 windows) |
| `ApproachRate` (AR) | Float | `0.0 - 10.0` | Approach circle speed and reaction time window |
| `SliderMultiplier` | Float | `0.4 - 3.6` | Base slider velocity multiplier (typically `1.4` - `2.0`) |
| `SliderTickRate` | Float | `0.5 - 8.0` | Frequency of slider ticks per beat (typically `1.0`) |

#### Difficulty Window Formulas:
- **Hit Circle Radius ($r$)**:
  $$r = 32 \times \left(1 - 0.7 \times \frac{\text{CS} - 5}{5}\right) = 54.4 - 4.48 \times \text{CS} \quad (\text{osupixels})$$
- **Approach Time ($\text{AR window in ms}$)**:
  - If $\text{AR} < 5$: $\text{Window} = 1200 + 600 \times (5 - \text{AR}) / 5 = 1800 - 120 \times \text{AR}$
  - If $\text{AR} = 5$: $\text{Window} = 1200\text{ ms}$
  - If $\text{AR} > 5$: $\text{Window} = 1200 - 750 \times (\text{AR} - 5) / 5 = 1200 - 150 \times (\text{AR} - 5)$
- **Hit Accuracy Window ($\text{OD in ms}$ for 300)**:
  $$\text{Window}_{300} = \pm (80 - 6 \times \text{OD})\text{ ms}$$

---

### 2.5 `[Events]`
Defines background images, video, breaks, and storyboard layers.

- **Background Line**:
  `0,0,"bg.jpg",0,0`
- **Break Period Line**:
  `2,startTime,endTime` (e.g. `2,45000,52000` indicates break from 45.0s to 52.0s).

---

### 2.6 `[TimingPoints]`
Timing points define BPM, beat subdivisions, hitsound volume, and slider velocity multipliers.

**Format**:
`time,beatLength,meter,sampleSet,sampleIndex,volume,uninherited,effects`

| Parameter | Type | Description |
|---|---|---|
| `time` | Integer | Millisecond timestamp when the timing point takes effect |
| `beatLength` | Float | - For **Uninherited (Red Line)**: Milliseconds per beat ($= 60000 / \text{BPM}$).<br>- For **Inherited (Green Line)**: Negative percentage for Slider Velocity multiplier ($= -100 / \text{SV multiplier}$). E.g., $-100 = 1.0\times\text{SV}$, $-50 = 2.0\times\text{SV}$, $-200 = 0.5\times\text{SV}$. |
| `meter` | Integer | Number of beats per measure (usually `4` for 4/4 time signature) |
| `sampleSet` | Integer | Default sample set: `0` = Default, `1` = Normal, `2` = Soft, `3` = Drum |
| `sampleIndex` | Integer | Custom sample set index (`0` = Default osu! sounds) |
| `volume` | Integer | Volume percentage: `0` to `100` |
| `uninherited` | Boolean/Int | `1` = Red timing point (BPM/offset anchor), `0` = Green timing point (SV/volume anchor) |
| `effects` | Integer | Bit flags: `1` = Kiai mode enabled, `8` = Omit first bar line |

---

### 2.7 `[Colours]`
Custom combo colour definitions in RGB format.

```text
Combo1 : 245,245,245
Combo2 : 120,180,250
Combo3 : 255,140,80
SliderTrackOverride : 30,30,30
SliderBorder : 255,255,255
```

---

## 3. Hit Objects Specification (`[HitObjects]`)

Hit objects are defined line-by-line in chronological order.

### 3.1 Object Type Bitmask

| Bit | Value | Meaning |
|---|---|---|
| 0 | `1` | Hit Circle |
| 1 | `2` | Slider |
| 2 | `4` | New Combo (NC) |
| 3 | `8` | Spinner |
| 4-6 | `16, 32, 64` | Combo Colour Skip count (0 to 7) |
| 7 | `128` | osu!mania Hold note (unused in standard) |

*Examples*:
- `1` = Hit circle (continue combo)
- `5` = Hit circle (new combo: $1 + 4$)
- `2` = Slider (continue combo)
- `6` = Slider (new combo: $2 + 4$)
- `12` = Spinner (new combo: $8 + 4$)

### 3.2 Hit Sound Bitmask

| Bit | Value | Sound Sample |
|---|---|---|
| 0 | `0` | Normal / Default hit sound |
| 1 | `2` | Whistle |
| 2 | `4` | Finish |
| 3 | `8` | Clap |

Combinations are additive: e.g., `6` = Whistle + Finish ($2 + 4$), `10` = Whistle + Clap ($2 + 8$).

---

## 4. Object Type Details

### 4.1 Hit Circle
Syntax:
`x,y,time,type,hitSound,hitSample`

*Example*:
`256,192,12500,1,0,0:0:0:0:`
- `x=256, y=192`: Position at playfield center.
- `time=12500`: 12.5 seconds.
- `type=1`: Hit circle.
- `hitSound=0`: Normal hitsound.
- `hitSample=0:0:0:0:`: Default sample assignment (`normalSet:additionSet:index:volume:customFilename`).

---

### 4.2 Slider
Syntax:
`x,y,time,type,hitSound,curveType|curvePoints,slides,length,edgeSounds,edgeSets,hitSample`

- **`curveType`**: Single character identifier:
  - `L` = Linear (straight line between points)
  - `P` = Perfect Circle / Circular arc (requires exactly 3 control points including start)
  - `B` = Bézier curve (arbitrary control points; repeating a point creates a sharp corner/red anchor)
  - `C` = Catmull-Rom (legacy spline interpolation)
- **`curvePoints`**: Pipe-separated `x:y` coordinates for slider path nodes (e.g. `200:150|250:200|300:150`).
- **`slides`**: Number of times the slider is traversed (`1` = single traverse, `2` = one reverse arrow, `3` = two reverses).
- **`length`**: Spatial pixel length of the slider body along its path (in osupixels).
- **`edgeSounds`**: Pipe-separated list of hitsound bitmasks for each slider edge (head, reverse arrows, tail). Length must equal `slides + 1`.
- **`edgeSets`**: Pipe-separated list of `normalSet:additionSet` for each edge. Length must equal `slides + 1`.

*Slider Duration Formula*:
$$\text{Duration (ms)} = \frac{\text{length}}{\text{SliderMultiplier} \times 100 \times \text{SV}} \times \text{beatLength}$$
where $\text{SV} = -100 / \text{beatLength}_{\text{inherited}}$ (default $1.0$ if no inherited timing point).

*Example*:
`128,96,24000,2,2,B|180:120|220:80|280:100,1,175.0,2|0,0:0|0:0,0:0:0:0:`

---

### 4.3 Spinner
Syntax:
`x,y,time,type,hitSound,endTime,hitSample`

- **`x, y`**: In standard osu!, coordinates are conventionally set to `256,192` (center).
- **`endTime`**: Millisecond timestamp when the spinner ends.

*Example*:
`256,192,60000,12,8,65000,0:0:0:0:`

---

## 5. Playfield Coordinate System & Constraints

```
(0,0) +----------------------------------------------+ (512,0)
      |                                              |
      |   Standard osu! Coordinate Space             |
      |   Width  : 512 osupixels                     |
      |   Height : 384 osupixels                     |
      |                                              |
      |             (256, 192) Playfield Center      |
      |                                              |
(0,384)+----------------------------------------------+ (512,384)
```

1. **Resolution & Boundaries**:
   - The native coordinate space is fixed at **512 x 384**.
   - All hit circle centers, slider anchor nodes, and spinner positions must be integers or clean floats within $0 \le x \le 512$ and $0 \le y \le 384$.

2. **Safe Screen Margin / Padding**:
   - Hit objects must not place circle edges offscreen.
   - For a given Circle Size (CS), the required border margin is:
     $$\text{Margin} \ge r = 54.4 - 4.48 \times \text{CS}$$
   - For CS 4.0: $r \approx 36.5\text{ px}$. Minimum safe coordinate box: $x \in [37, 475]$, $y \in [37, 347]$.

3. **Hit Object Stacking**:
   - Objects placed at identical or nearly identical positions within a small time window ($t < \text{stackLeniency} \times \text{AR window}$) will visually stack along a diagonal offset determined by the client engine.
