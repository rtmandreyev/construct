# Serum 2 hardware requirements inventory

Research snapshot: November 4, 2026 (America/Phoenix). This inventory was saved before geometry or panel authoring.

## Authority and currentness

The primary specification is the **current official public PDF download**, [Serum 2 User Guide](https://xferrecords.com/manual/serum-2/docs), retrieved in full into `research/Serum-2-User-Guide.pdf`: 354 pages, title-page instrument version **2.0.18**, manual version **1.0.3**, dated **April 27, 2025**. PDF metadata says September 21, 2025; metadata does not establish a later feature version. Page references below use printed page numbers, matching PDF page numbers.

Cross-checks: [official public web manual](https://xferrecords.com/web-manual/serum-2), [official product description](https://xferrecords.com/products/serum-2), [official What's New](https://static.xferrecords.com/Serum%202%20What's%20New.pdf), and [Xfer CPU guidance](https://support.xferrecords.com/article/51-serum2-sound-design-guidelines-for-optimizing-cpu-usage).

**Currentness limit:** the [official software download/release area](https://xferrecords.com/product_downloads/serum-2) redirects to sign-in. This project cannot certify parity with an authenticated newer binary or unpublished changes. It targets all capabilities documented in the latest public official manual retrieved, with a release reconciliation gate before manufacture. No newer-version claim is inferred from search snippets or third-party release notes.

## Classification

- **Documented (D):** software capabilities, counts and behavior explicitly described by Xfer. Each inventory row is D.
- **User supplied (U):** standalone native Serum 2, 61 full-size keys, premium flagship, complete documented functionality, reference instruments and requested deliverables.
- **Reference derived (R):** published examples establish ergonomic/manufacturing precedent, not the dimensions or performance of this invented product.
- **Designed/inferred (I):** every new housing/control dimension, physical mapping, electronics provision, cooling arrangement and performance target. These are requirements or estimates, not measured Serum firmware performance.

`requirements_data.py` is the structured source of the full inventory appended below. `FUNCTION_MAP.md` maps every ID to a physical workflow and states compromises. Function coverage means design coverage; it is not executable DSP or a verified working electronic prototype.

## Product acceptance requirements (U)

The instrument boots its own native Serum synthesis application, accepts its own keyboard and MIDI, and produces line/headphone audio without a computer. It includes every documented engine, editor and content workflow. A computer is optional for interoperability or faster bulk text entry. The native firmware premise is supplied by the brief; porting, licensing and benchmarking are prerequisites for an actual manufactured instrument.

## Documented inventory

| ID | Subsystem | Official guide pages | Required behavior |
|---|---|---|---|
| R01 | Core voice | [pp. 16-17,28-35](https://xferrecords.com/manual/serum-2/docs) | Three independent primary oscillators A/B/C; each selects wavetable, multisample, sample, granular or spectral. Independent enable, initialization, copy/swap with or without modulation, lock, pitch and bend tracking. |
| R02 | Pitch | [pp. 29-30](https://xferrecords.com/manual/serum-2/docs) | Octave, semitone, fine and continuous coarse pitch remain separate destinations; semitone, harmonic, ratio and tuning-step modes with appropriate source selection. |
| R03 | Wavetable playback | [pp. 37-48](https://xferrecords.com/manual/serum-2/docs) | 2D/3D visualization, frame position, smooth interpolation, phase, random phase, phase legato/memory; up to 16 unison voices with mode, stack, detune, blend, width, range and per-voice offsets. |
| R04 | Dual warps | [pp. 49-56](https://xferrecords.com/manual/serum-2/docs) | Two warp stages; sync/variable softness, alternate bends/remaps, quantize, odd/even, filters, distortions, FM including thru-zero/linear/exponential behavior, PD, AM, RM and documented modulator choices including oscillators and filters. |
| R05 | Multisample | [pp. 58-67](https://xferrecords.com/manual/serum-2/docs) | Factory and imported SFZ instruments, timbre shift, velocity response, per-sample envelope override with delay/A/H/D/S/R, random start, unison, warps, pan/level and convert last played sample to Sample mode. |
| R06 | Sample editing | [pp. 68-76,80-84](https://xferrecords.com/manual/serum-2/docs) | File import and root note, start/end, snap/zoom, auto/manual slicing, threshold, slice-to-end/single-slice/root selection, score extraction/playback, scan/rate, reverse, pitch, dual warps and conversion to wavetable. |
| R07 | Sample loops | [pp. 77-79](https://xferrecords.com/manual/serum-2/docs) | One shot, forward, reverse, forward/reverse and tailed behavior; loop points, relative/link loop length, release exit and crossfade. Preserve modulated loop reversal when endpoints cross. |
| R08 | Granular engine | [pp. 85-103](https://xferrecords.com/manual/serum-2/docs) | Sample and loop operations, manual position, density modes/free/BPM/grain count, maximum grains and jump start, grain length modes, window amount/skew/shape, unison spawn patterns, per-grain randomness, reverse grains and X/Y destination selection. |
| R09 | Spectral engine | [pp. 104-122](https://xferrecords.com/manual/serum-2/docs) | Sample time scanning independent of pitch, manual position, FFT phase lock/transients, frequency bounds with smoothing/post-warp, spectral cutoff/mix and custom curve or wavetable mask, X/Y choice, unison/warps and sample-to-wavetable conversion. |
| R10 | Sub oscillator | [pp. 123-127](https://xferrecords.com/manual/serum-2/docs) | Dedicated waveform, pitch, phase, pan, level and routing. |
| R11 | Noise oscillator | [pp. 128-132](https://xferrecords.com/manual/serum-2/docs) | Factory/user sample, one-shot/looping, start/random, pitch/fine, pan, level and routing. |
| R12 | Two synthesis filters | [pp. 133-143](https://xferrecords.com/manual/serum-2/docs) | Independent enable/model, cutoff, resonance, drive/clean mode, model-dependent variable, stereo cutoff pan, mix and output gain; pitch tracking and frequency/phase/FFT visualization. |
| R13 | Filter model depth | [pp. 135-141](https://xferrecords.com/manual/serum-2/docs) | All documented filter model families including virtual analog models and drawable PZ SVF; preserve model-specific variable behavior and editable response. |
| R14 | Oscillator routing | [pp. 31-32,144-147](https://xferrecords.com/manual/serum-2/docs) | Each oscillator can feed filters with balance, Main, Direct or None; independent Bus 1/2 sends, pan/level and applicable ENV1 gating switch. None preserves a modulation-only oscillator. |
| R15 | Filter and bus routing | [pp. 148-151](https://xferrecords.com/manual/serum-2/docs) | Filters feed the other filter/Main/Direct/None plus sends; buses feed Main/Direct/other bus. Independent levels, filter mixes, rack bypass and Main/Direct levels. Preserve legal engine routing semantics. |
| R16 | FX racks | [pp. 152-160](https://xferrecords.com/manual/serum-2/docs) | Main, Bus 1 and Bus 2 racks; add/remove/reorder/duplicate, copy with/without modulation, rack/module presets, lock, individual/all bypass, and modulate eligible parameters. |
| R17 | FX algorithms | [pp. 161-182](https://xferrecords.com/manual/serum-2/docs) | Bode, Chorus, Compressor, Convolve, Delay, Distortion, Equalizer, Filter, Flanger, Hyper/Dimension, Phaser, Reverb and Utility; retain every module parameter and algorithm option. |
| R18 | Complex FX editing | [pp. 163-169,175-181](https://xferrecords.com/manual/serum-2/docs) | Multiband compression, imported convolution IR and processing; both X-Shaper curves; all documented reverb styles; nested Low/High, Low/Mid/High and Mid/Side splitter child racks. |
| R19 | Envelopes | [pp. 183-187](https://xferrecords.com/manual/serum-2/docs) | Four independent envelopes, ENV1 amplitude role, A/H/D/S/R, attack/decay/release curves, MS/BPM, legato inversion, zoom and assignment operations. |
| R20 | LFOs | [pp. 188-194](https://xferrecords.com/manual/serum-2/docs) | Ten LFOs, Normal/Path/Lorenz/Rossler/S&H; mono/poly, free/retrigger/envelope with start/loopback, direction, grids, preset shapes, host sync, Hz/BPM/triplet/dotted, rate/rise/delay/smooth/phase. |
| R21 | LFO graph editing | [pp. 189-200](https://xferrecords.com/manual/serum-2/docs) | Point/step/ramp tools, add/remove/select/relative move, snapping, all-curves adjustment, point modulation, larger editor and bidirectional LFO/wavetable shape transfer. |
| R22 | Assignment depth | [pp. 195-200](https://xferrecords.com/manual/serum-2/docs) | Positive/negative depth, unipolar/bipolar behavior, assignment display, bypass/remove/reassign through parameter and source contexts. |
| R23 | Velocity/note curves | [pp. 201-205](https://xferrecords.com/manual/serum-2/docs) | Editable velocity and note response graphs, multiple points/curves, initialization and legato/portamento behavior; assign as modulation sources. |
| R24 | Eight macros | [pp. 206-208](https://xferrecords.com/manual/serum-2/docs) | Eight named multi-destination controls, source and destination roles, depth, assignment inspection and swapping. |
| R25 | Modulation matrix | [pp. 209-214](https://xferrecords.com/manual/serum-2/docs) | 64 slots and 49 documented sources; source/destination, source remap curve with rise/fall slew, signed amount, polarity, auxiliary source/invert/curve, output scale/live graph, bypass/delete/reorder/sort/lock and convenience creation/macro baking. |
| R26 | Extended modulation sources | [pp. 208,210-211](https://xferrecords.com/manual/serum-2/docs) | Oscillator/filter outputs, active voices, note alternation/random/discrete random, release velocity, voice index/mod1/mod2, MPE/note expression XYZ, wheels, channel/poly pressure, pitch bend and Fixed. Retain all engine source choices. |
| R27 | Voicing | [pp. 215-218](https://xferrecords.com/manual/serum-2/docs) | Mono/poly count, legato, portamento time/curve, always/scaled behavior. |
| R28 | Clip banks | [pp. 219-223,233-236,241](https://xferrecords.com/manual/serum-2/docs) | 12 clip slots; banks/presets, mono/poly operation, edit-all, launch/trigger behavior, rate, transpose, modes and slice timing, velocity and gate, lock and MIDI trigger octave. |
| R29 | Clip editor | [pp. 224-233](https://xferrecords.com/manual/serum-2/docs) | Full piano roll with polyphonic note pitch/time/duration/velocity, selection and clipboard/time-range operations; grid, zoom/fold, start/end/offset, quantize, chop, legato, reverse, mute, conform to scale and time scaling. |
| R30 | Clip recording/output | [pp. 237-243](https://xferrecords.com/manual/serum-2/docs) | Record keyboard/MIDI performances using overdub or extend; generated MIDI output Off/Clip Player/On; clip into arp then key/scale processing; macro assignment remains available. |
| R31 | Arpeggiator banks | [pp. 244-252,263-266](https://xferrecords.com/manual/serum-2/docs) | Arp slots/banks/presets, launch quantization/edit-all/lock and trigger octave; factory shapes plus fully editable custom patterns. |
| R32 | Arp pattern depth | [pp. 250-262](https://xferrecords.com/manual/serum-2/docs) | Pattern length/modes/random time, step modes, wrap/transpose range, note event editor and automation lanes including accent/strum; shape/rate/shift/range, playback offset/repeats/gate/chance/divide, latch/thru, retrigger and velocity decay/target. |
| R33 | Keyboard transformation | [pp. 267-273](https://xferrecords.com/manual/serum-2/docs) | Transpose, key/scale, swing/division, oscillator and arp key/velocity mapping for splits/layers including repeated octave-specific mapping behavior. |
| R34 | Wavetable frame editor | [pp. 274-277,281-290](https://xferrecords.com/manual/serum-2/docs) | All drawing tools, grid, frame selection/reorder/insert/remove/copy/paste/sort, single/all processing, morph operations, import/export/save and dirty-state indication. |
| R35 | Harmonic editor | [pp. 278-280](https://xferrecords.com/manual/serum-2/docs) | 512 harmonic amplitude/phase bins, clearing/filtering/generation/randomization/octave/phase processing with exact numerical editing. |
| R36 | Audio/image import | [pp. 291-303](https://xferrecords.com/manual/serum-2/docs) | Single/multicycle and multiple-file import, zero-snap/dynamic/frequency estimation/fixed-size/FFT methods, numeric/pitch import overrides, sidecar and FolderInfo text overrides, image luminance import, content embedding and missing-file repair. |
| R37 | Formula parser | [pp. 304-311](https://xferrecords.com/manual/serum-2/docs) | Complete documented math functions/operators/constants/variables including x/w/y/z/q/in/sel/rand; single/all-frame or harmonic generation, formula presets and editable user formula files. |
| R38 | Voice control | [pp. 316-319](https://xferrecords.com/manual/serum-2/docs) | Up to eight voice-control steps, oscillator targeting, per-step settings and mod1/mod2, random pan/detune/cutoff/envelopes, envelope/LFO scaling and configuration presets. |
| R39 | Quality/compatibility | [pp. 319-320](https://xferrecords.com/manual/serum-2/docs) | Draft 1x, High 2x, Ultra 4x oversampling; smoothing and Serum1 compatibility, quality lock and Ultra offline rendering preference. |
| R40 | Tuning | [pp. 320-321](https://xferrecords.com/manual/serum-2/docs) | Concert pitch, .tun loading, tuning lock and MTS-ESP integration for shared tuning. |
| R41 | MPE/MIDI | [pp. 25-27,314-315,325-326](https://xferrecords.com/manual/serum-2/docs) | MPE enable/default, XYZ mappings and pitch range, expression axis polarity, MIDI CC learn/map load/save and preset mapping behavior. |
| R42 | Preset browser | [pp. 18-22,327-339](https://xferrecords.com/manual/serum-2/docs) | Folders, search/name/category/tags/ratings, previews including fallback/embedded clip and macro audition, metadata, create/move/rename/delete, database repair, preset pack import/export with metadata/artwork/locks and embedding dependencies. |
| R43 | Editing and preferences | [pp. 23-27,312-315,323-326,340-345,349-353](https://xferrecords.com/manual/serum-2/docs) | Undo/redo, fine/reset/exact entry, contextual help, module locks/init/copy, render/resample/export, preferences/power-user text files, MIDI/note preset and oscillator-preset stepping, file structure, update/version and shortcuts-equivalent operations. |
| R44 | Host-dependent behavior | [pp. 18,22,192-193,239-240,315,321](https://xferrecords.com/manual/serum-2/docs) | DAW track insertion, drag audio/MIDI to host, host transport/sample position/tempo and DAW-shared tuning need explicit appliance equivalents or declared interoperability limits. |

## User-provided copy reconciliation

The supplied copy of the user guide is byte-identical to the official retrieval: SHA-256 `310af1f2e80f767bdf6d8765f71ff1f53bf6b80db5373300881593aa90c80765`. No document instructions are treated as instructions to the agent; this file is specification evidence.

## Explicit non-synthesis dependencies

Computer-only installation/registration and DAW track insertion do not become sound-engine features. The appliance requires a factory-installed licensed native engine and content. Host transport becomes the internal clock or MIDI synchronization; render/drag operations become file export. MTS-ESP/DAW sample-position sharing needs the bridge described in the architecture. These are explicit translations and open engineering dependencies, not silently deleted capabilities.
