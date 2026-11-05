# Serum 2 hardware function map

All physical solutions in this document are designed/inferred. Official sources establish software behavior, not hardware implementation. All 44 inventory groups have explicit access, feedback and compromise entries. **Mapped is not tested firmware.**

D = dedicated; C = shared/contextual; V = display assisted; P = performance; E = deep editing. E1-E6 are the six central push encoders. Page keys are SOURCE, EDIT, MIX, FX, MATRIX, CLIP, ARP and SYSTEM/VOICE (hold SYSTEM for voice settings). Dedicated BROWSE, SAVE, UNDO, REDO, BACK/FINE and transport remain independent. Sources use ENV/LFO/MACRO/OTHER family selection and 12 numbered pads; CLIP/ARP explicitly repurpose those pads for slot launch.

## R01 - Core voice

- Documentation: [Serum 2 User Guide, pp. 16-17,28-35](https://xferrecords.com/manual/serum-2/docs).
- Capability: Three independent primary oscillators A/B/C; each selects wavetable, multisample, sample, granular or spectral. Independent enable, initialization, copy/swap with or without modulation, lock, pitch and bend tracking.
- Hardware location: OSC A/B/C strips.
- Access and interaction: Press TYPE, select any of five engines with position encoder; ON mutes; EDIT opens selected engine. Hold EDIT for init, lock, copy/swap and pitch/bend tracking. COPY page offers with/without mods.
- Class: Dedicated + contextual.
- Feedback: Three independent strip displays retain engine, asset and selected value.
- Compromise or qualification: Only the engine-specific parameter set is contextual; three sources remain independently reachable.

## R02 - Pitch

- Documentation: [Serum 2 User Guide, pp. 29-30](https://xferrecords.com/manual/serum-2/docs).
- Capability: Octave, semitone, fine and continuous coarse pitch remain separate destinations; semitone, harmonic, ratio and tuning-step modes with appropriate source selection.
- Hardware location: Each OSC strip PITCH; EDIT/Pitch.
- Access and interaction: PITCH turns semitones; push selects OCT/SEM/FIN/CRS in explicit strip list. EDIT shows all four concurrently on E1-E4; E5 selects tuning mode, E6 source/ratio.
- Class: Dedicated + contextual.
- Feedback: Separate parameter identities and modulation destinations; current unit and mode on strip.
- Compromise or qualification: One physical pitch shaft serves four independent parameters; no merged pitch destination.

## R03 - Wavetable playback

- Documentation: [Serum 2 User Guide, pp. 37-48](https://xferrecords.com/manual/serum-2/docs).
- Capability: 2D/3D visualization, frame position, smooth interpolation, phase, random phase, phase legato/memory; up to 16 unison voices with mode, stack, detune, blend, width, range and per-voice offsets.
- Hardware location: OSC POSITION, UNISON, DETUNE; EDIT/Voice.
- Access and interaction: Position scans frames; unison and detune immediate. EDIT/Voice exposes phase, random, memory, blend/stack/width/range/offsets on named E1-E6 banks.
- Class: Dedicated + display assisted.
- Feedback: Strip frame number and mini waveform; editor offers 2D/3D and unison spread.
- Compromise or qualification: Six controls page the remaining unison settings. All documented modes remain selectable.

## R04 - Dual warps

- Documentation: [Serum 2 User Guide, pp. 49-56](https://xferrecords.com/manual/serum-2/docs).
- Capability: Two warp stages; sync/variable softness, alternate bends/remaps, quantize, odd/even, filters, distortions, FM including thru-zero/linear/exponential behavior, PD, AM, RM and documented modulator choices including oscillators and filters.
- Hardware location: OSC WARP1/WARP2; EDIT/Warp.
- Access and interaction: Turn each amount; push opens algorithm/source. EDIT exposes variable/remap curve. Use common node editor to draw or numerically set remaps.
- Class: Dedicated + deep editing.
- Feedback: Algorithm names always shown in the oscillator overview and strip context; selected stage highlighted.
- Compromise or qualification: Complex curves use the shared graph editor rather than dedicated hardware for every vertex.

## R05 - Multisample

- Documentation: [Serum 2 User Guide, pp. 58-67](https://xferrecords.com/manual/serum-2/docs).
- Capability: Factory and imported SFZ instruments, timbre shift, velocity response, per-sample envelope override with delay/A/H/D/S/R, random start, unison, warps, pan/level and convert last played sample to Sample mode.
- Hardware location: OSC TYPE/Multisample; BROWSE asset focus.
- Access and interaction: Load SFZ with paths/dependencies from internal storage or USB. EDIT/Envelope exposes override and DAHDSR, velocity and random; contextual timbre; convert last note via Operations.
- Class: Contextual + deep editing.
- Feedback: Zone/sample status, override marker and envelope overlay.
- Compromise or qualification: Bulk SFZ authoring uses the onboard text/file editor or imported SFZ; editing does not require a computer.

## R06 - Sample editing

- Documentation: [Serum 2 User Guide, pp. 68-76,80-84](https://xferrecords.com/manual/serum-2/docs).
- Capability: File import and root note, start/end, snap/zoom, auto/manual slicing, threshold, slice-to-end/single-slice/root selection, score extraction/playback, scan/rate, reverse, pitch, dual warps and conversion to wavetable.
- Hardware location: OSC TYPE/Sample; EDIT/Sample.
- Access and interaction: POSITION becomes scan/rate; E1-E4 edit playback/loop endpoints, E5 crossfade and E6 zoom. Operations selects snap/slice; slice index/threshold and root fields are explicit. Extract score writes a clip via the engine operation.
- Class: Contextual + display assisted.
- Feedback: Waveform with selected and modulated boundaries, slice markers and numerical units.
- Compromise or qualification: Large sample surgery is slower than a desktop mouse; optional touch selection and exact encoder positioning coexist.

## R07 - Sample loops

- Documentation: [Serum 2 User Guide, pp. 77-79](https://xferrecords.com/manual/serum-2/docs).
- Capability: One shot, forward, reverse, forward/reverse and tailed behavior; loop points, relative/link loop length, release exit and crossfade. Preserve modulated loop reversal when endpoints cross.
- Hardware location: EDIT/Sample/Loop.
- Access and interaction: Choose mode and relative/link/release flags with E1-E6 page; select either endpoint then assign modulation using ASSIGN.
- Class: Contextual.
- Feedback: Loop direction, crossfade curve and endpoint values remain visible.
- Compromise or qualification: Endpoint crossing is allowed and shown as direction reversal, not silently clamped.

## R08 - Granular engine

- Documentation: [Serum 2 User Guide, pp. 85-103](https://xferrecords.com/manual/serum-2/docs).
- Capability: Sample and loop operations, manual position, density modes/free/BPM/grain count, maximum grains and jump start, grain length modes, window amount/skew/shape, unison spawn patterns, per-grain randomness, reverse grains and X/Y destination selection.
- Hardware location: OSC TYPE/Granular; EDIT/Grains/Window/Random.
- Access and interaction: Position/scan remains immediate; contextual six knobs expose density, length, count and window; further banks expose spawn and all grain randomness. XY ribbon can control position and the chosen documented Y destination.
- Class: Dedicated + contextual + deep editing.
- Feedback: Animated grain positions, density/limit, window plot and XY destination name.
- Compromise or qualification: Full randomness and window-shape sets need named banks. No grain or engine type is removed.

## R09 - Spectral engine

- Documentation: [Serum 2 User Guide, pp. 104-122](https://xferrecords.com/manual/serum-2/docs).
- Capability: Sample time scanning independent of pitch, manual position, FFT phase lock/transients, frequency bounds with smoothing/post-warp, spectral cutoff/mix and custom curve or wavetable mask, X/Y choice, unison/warps and sample-to-wavetable conversion.
- Hardware location: OSC TYPE/Spectral; EDIT/Spectral/Mask.
- Access and interaction: Context controls select scan, cutoff, mix, frequency boundaries, phase lock/transients and post-warp. Mask uses node editor or wavetable browser. XY ribbon binds position and documented Y choice.
- Class: Contextual + display assisted.
- Feedback: Spectrogram, bounds, transient state and mask curve; separate time/pitch values.
- Compromise or qualification: Spectral visualization shares the editor with other deep operations; it is not a permanent second spectrogram.

## R10 - Sub oscillator

- Documentation: [Serum 2 User Guide, pp. 123-127](https://xferrecords.com/manual/serum-2/docs).
- Capability: Dedicated waveform, pitch, phase, pan, level and routing.
- Hardware location: SOURCE page/Sub.
- Access and interaction: Press SOURCE then Sub; E1-E6 provide waveform/pitch/phase/pan/level/route. Press the header soft key to enable/disable.
- Class: Shared/contextual.
- Feedback: Sub badge and meter in signal-flow overview; status retained across page changes.
- Compromise or qualification: Sub has no separate permanent knob bank; access is one page key and one soft key.

## R11 - Noise oscillator

- Documentation: [Serum 2 User Guide, pp. 128-132](https://xferrecords.com/manual/serum-2/docs).
- Capability: Factory/user sample, one-shot/looping, start/random, pitch/fine, pan, level and routing.
- Hardware location: SOURCE page/Noise.
- Access and interaction: SOURCE then Noise; sample browser and named banks expose one-shot, start/random, pitch/fine, pan, gain and route.
- Class: Shared/contextual.
- Feedback: Noise asset, waveform/one-shot state and meter in overview.
- Compromise or qualification: Noise shares the Sub access area; sample operations retain full engine behavior.

## R12 - Two synthesis filters

- Documentation: [Serum 2 User Guide, pp. 133-143](https://xferrecords.com/manual/serum-2/docs).
- Capability: Independent enable/model, cutoff, resonance, drive/clean mode, model-dependent variable, stereo cutoff pan, mix and output gain; pitch tracking and frequency/phase/FFT visualization.
- Hardware location: FILTER 1/2 strips.
- Access and interaction: Six persistent controls per filter: cutoff, resonance, drive, model-dependent VAR, pan and mix. Push cutoff selects model; ON/ROUTE buttons; output gain and pitch track in filter EDIT.
- Class: Dedicated + contextual.
- Feedback: Two filter displays show model and VAR name; editor frequency/phase/FFT overlay.
- Compromise or qualification: Output gain and clean mode are contextual. PAN is correctly stereo cutoff offset rather than mixer pan.

## R13 - Filter model depth

- Documentation: [Serum 2 User Guide, pp. 135-141](https://xferrecords.com/manual/serum-2/docs).
- Capability: All documented filter model families including virtual analog models and drawable PZ SVF; preserve model-specific variable behavior and editable response.
- Hardware location: Filter model browser; EDIT/Response.
- Access and interaction: All engine models listed by official family, not a curated subset. PZ response edit uses pole/zero node selection, position/value encoders, add/remove and optional touch.
- Class: Display assisted + deep editing.
- Feedback: Model-specific response, VAR name and active transfer function.
- Compromise or qualification: Exact PZ editing UX needs validation against shipping engine data; no replacement generic filter is proposed.

## R14 - Oscillator routing

- Documentation: [Serum 2 User Guide, pp. 31-32,144-147](https://xferrecords.com/manual/serum-2/docs).
- Capability: Each oscillator can feed filters with balance, Main, Direct or None; independent Bus 1/2 sends, pan/level and applicable ENV1 gating switch. None preserves a modulation-only oscillator.
- Hardware location: Each oscillator ROUTE; MIX page.
- Access and interaction: ROUTE opens source-specific routing: E1 target, E2 F1/F2 balance, E3 Bus1 send, E4 Bus2 send, E5 level, E6 ENV1 gate. PAN remains dedicated.
- Class: Dedicated entry + contextual.
- Feedback: Signal-flow display and destination meters; None explicitly labeled MOD ONLY.
- Compromise or qualification: No panel normalization forces serial flow. Engine-valid route choices define the graph.

## R15 - Filter and bus routing

- Documentation: [Serum 2 User Guide, pp. 148-151](https://xferrecords.com/manual/serum-2/docs).
- Capability: Filters feed the other filter/Main/Direct/None plus sends; buses feed Main/Direct/other bus. Independent levels, filter mixes, rack bypass and Main/Direct levels. Preserve legal engine routing semantics.
- Hardware location: MIX page; FILTER ROUTE; FX bus selection.
- Access and interaction: Select oscillator/filter/bus in graph with navigator. Six controls expose target, sends, pan/mix/level and gate as applicable. Main/Direct levels separate.
- Class: Display assisted + contextual.
- Feedback: Route arrows encode signal magnitude; label identifies stereo Main/Direct and Bus1/2.
- Compromise or qualification: Hardware AUX outputs are assignable taps; Direct is first an internal engine route, not automatically a jack.

## R16 - FX racks

- Documentation: [Serum 2 User Guide, pp. 152-160](https://xferrecords.com/manual/serum-2/docs).
- Capability: Main, Bus 1 and Bus 2 racks; add/remove/reorder/duplicate, copy with/without modulation, rack/module presets, lock, individual/all bypass, and modulate eligible parameters.
- Hardware location: FX page and six contextual encoders.
- Access and interaction: Select MAIN/BUS1/BUS2 with soft keys; navigator selects module; ADD/COPY/MOVE/BYPASS/REMOVE operations. COPY explicitly includes/excludes mods. Hold rack tab for lock/preset operations.
- Class: Contextual + deep editing.
- Feedback: Rack tree with breadcrumb, instance names, modulation badges and per-rack meter.
- Compromise or qualification: No fixed number of physical effect slots; UI lists all engine-supported instances.

## R17 - FX algorithms

- Documentation: [Serum 2 User Guide, pp. 161-182](https://xferrecords.com/manual/serum-2/docs).
- Capability: Bode, Chorus, Compressor, Convolve, Delay, Distortion, Equalizer, Filter, Flanger, Hyper/Dimension, Phaser, Reverb and Utility; retain every module parameter and algorithm option.
- Hardware location: FX module parameter pages.
- Access and interaction: Selected module presents E1-E6 named parameters in stable, numbered pages. Every current engine parameter is enumerable; push jumps to type/unit/exact entry.
- Class: Contextual.
- Feedback: Graph and six parameter name/value tiles; page count and instance path visible.
- Compromise or qualification: Large modules need more than one bank. Depth remains intact.

## R18 - Complex FX editing

- Documentation: [Serum 2 User Guide, pp. 163-169,175-181](https://xferrecords.com/manual/serum-2/docs).
- Capability: Multiband compression, imported convolution IR and processing; both X-Shaper curves; all documented reverb styles; nested Low/High, Low/Mid/High and Mid/Side splitter child racks.
- Hardware location: FX tree; EDIT/Curve or IR Browser.
- Access and interaction: Splitter enter descends to child rack; BACK ascends. Convolve loads user IR; compressor shows crossovers. X-Shaper A/B and every reverb style have explicit pages.
- Class: Deep editing + display assisted.
- Feedback: Persistent breadcrumb such as BUS1 > L/M/H > MID > Distortion; editable curves and gain reduction.
- Compromise or qualification: No flattening of nested racks. Navigation cost grows with the actual patch depth.

## R19 - Envelopes

- Documentation: [Serum 2 User Guide, pp. 183-187](https://xferrecords.com/manual/serum-2/docs).
- Capability: Four independent envelopes, ENV1 amplitude role, A/H/D/S/R, attack/decay/release curves, MS/BPM, legato inversion, zoom and assignment operations.
- Hardware location: ENV source family; 12 source pads; five envelope faders.
- Access and interaction: ENV then pad 1-4 chooses envelope. Five 65mm nonmotorized faders control A/H/D/S/R with soft pickup. CURVE opens attack/decay/release curvature; units and legato inversion in source options.
- Class: Dedicated + contextual.
- Feedback: Envelope selection, graph, physical pickup arrows and ENV1 amp badge.
- Compromise or qualification: One set of five faders serves four envelopes; pickup avoids jumps, at cost of crossing stored position.

## R20 - LFOs

- Documentation: [Serum 2 User Guide, pp. 188-194](https://xferrecords.com/manual/serum-2/docs).
- Capability: Ten LFOs, Normal/Path/Lorenz/Rossler/S&H; mono/poly, free/retrigger/envelope with start/loopback, direction, grids, preset shapes, host sync, Hz/BPM/triplet/dotted, rate/rise/delay/smooth/phase.
- Hardware location: LFO source family; pads 1-10; source edit page.
- Access and interaction: LFO then numbered pad; EDIT opens type/mode/rate/phase/rise/delay/smooth and grid/host/mono/direction banks.
- Class: Dedicated selection + contextual.
- Feedback: All ten remain addressable from init; source tile shows index, rate, phase and destination count.
- Compromise or qualification: Hardware exposes 7-10 immediately rather than hiding unused LFOs; DSP behavior is preserved.

## R21 - LFO graph editing

- Documentation: [Serum 2 User Guide, pp. 189-200](https://xferrecords.com/manual/serum-2/docs).
- Capability: Point/step/ramp tools, add/remove/select/relative move, snapping, all-curves adjustment, point modulation, larger editor and bidirectional LFO/wavetable shape transfer.
- Hardware location: EDIT/LFO graph; shared E1-E6.
- Access and interaction: Navigator selects node or multiselection; E1 index, E2 X, E3 Y, E4 curvature, E5 grid, E6 zoom. ADD/DELETE/DRAW/SNAP in soft-key tools; relative/all-curves actions explicit. ASSIGN to selected point chooses X/Y and LFO bus. Shape-transfer action targets wavetable/LFO.
- Class: Deep editing + optional touch.
- Feedback: Selected nodes, bus names, motion range and live output trace.
- Compromise or qualification: Freehand curves benefit from optional touch; every operation has encoder/menu access. LFO buses are distinguished from audio Bus1/2.

## R22 - Assignment depth

- Documentation: [Serum 2 User Guide, pp. 195-200](https://xferrecords.com/manual/serum-2/docs).
- Capability: Positive/negative depth, unipolar/bipolar behavior, assignment display, bypass/remove/reassign through parameter and source contexts.
- Hardware location: ASSIGN/AMOUNT/INSPECT/POLAR/CURVE controls.
- Access and interaction: Select source, press ASSIGN, press destination encoder (or select display field). Turn signed AMOUNT; POLAR toggles unipolar/bipolar. INSPECT lists every assignment on that destination. Delete/bypass/reassign act on selected row.
- Class: Dedicated + display assisted.
- Feedback: Selected source name, destination, signed depth, polarity, source count and live ring arc.
- Compromise or qualification: ASSIGN mode intercepts encoder press without changing the base parameter; touching or turning alone does not create accidental routes.

## R23 - Velocity/note curves

- Documentation: [Serum 2 User Guide, pp. 201-205](https://xferrecords.com/manual/serum-2/docs).
- Capability: Editable velocity and note response graphs, multiple points/curves, initialization and legato/portamento behavior; assign as modulation sources.
- Hardware location: OTHER source browser > Velocity/Note.
- Access and interaction: Select the curve, use common node editor, set legato option then assign with ASSIGN.
- Class: Contextual + deep editing.
- Feedback: Curve, current input value and output cursor.
- Compromise or qualification: Response graphs are edited on the central display.

## R24 - Eight macros

- Documentation: [Serum 2 User Guide, pp. 206-208](https://xferrecords.com/manual/serum-2/docs).
- Capability: Eight named multi-destination controls, source and destination roles, depth, assignment inspection and swapping.
- Hardware location: Eight front-edge macro encoders and label strip.
- Access and interaction: All eight always available; press chooses macro as modulation source. ASSIGN can also select a macro as destination; Operations swaps/bakes mappings.
- Class: Performance + dedicated.
- Feedback: Eight patch-defined names, ring values, destination counts in inspection.
- Compromise or qualification: Endless encoders replace software knobs without storing physical pointer mismatch.

## R25 - Modulation matrix

- Documentation: [Serum 2 User Guide, pp. 209-214](https://xferrecords.com/manual/serum-2/docs).
- Capability: 64 slots and 49 documented sources; source/destination, source remap curve with rise/fall slew, signed amount, polarity, auxiliary source/invert/curve, output scale/live graph, bypass/delete/reorder/sort/lock and convenience creation/macro baking.
- Hardware location: INSPECT/MATRIX page and modulation controls.
- Access and interaction: Navigator chooses among 64 rows; E1 source, E2 destination, E3 aux, E4 aux inverse, E5 output, E6 row/bypass. Signed depth uses AMOUNT. CURVE selects main/aux remap and rise/fall. Operations reorder/sort/lock, vibrato, velocity-amp and bake.
- Class: Dedicated entry + deep editing.
- Feedback: Full row with source/aux/output curves and numeric values; occupancy meter, bypass and lock visible.
- Compromise or qualification: At 64 routes, search/filter plus paging replaces a full desktop matrix. No assignment cap below the documented 64.

## R26 - Extended modulation sources

- Documentation: [Serum 2 User Guide, pp. 208,210-211](https://xferrecords.com/manual/serum-2/docs).
- Capability: Oscillator/filter outputs, active voices, note alternation/random/discrete random, release velocity, voice index/mod1/mod2, MPE/note expression XYZ, wheels, channel/poly pressure, pitch bend and Fixed. Retain all engine source choices.
- Hardware location: OTHER source browser; module source selector.
- Access and interaction: All 49 documented source choices enumerate from the native engine, with categories for voice/note/random/expression/audio/fixed. Oscillator/filter sources can also be selected from their header context.
- Class: Contextual.
- Feedback: Source label includes poly/mono/audio category and current value.
- Compromise or qualification: Raw audio-source modulation is firmware behavior; control scanner does not synthesize the audio-rate signal.

## R27 - Voicing

- Documentation: [Serum 2 User Guide, pp. 215-218](https://xferrecords.com/manual/serum-2/docs).
- Capability: Mono/poly count, legato, portamento time/curve, always/scaled behavior.
- Hardware location: VOICE page; persistent header status.
- Access and interaction: VOICE then mono/legato/poly/steal/same-note limit and porta banks; choose curve/always/scaled without replacing other settings.
- Class: Contextual.
- Feedback: Mono/poly/legato status, active count and glide curve.
- Compromise or qualification: Less frequent voice setup is one page away; no unsupported fixed polyphony guarantee.

## R28 - Clip banks

- Documentation: [Serum 2 User Guide, pp. 219-223,233-236,241](https://xferrecords.com/manual/serum-2/docs).
- Capability: 12 clip slots; banks/presets, mono/poly operation, edit-all, launch/trigger behavior, rate, transpose, modes and slice timing, velocity and gate, lock and MIDI trigger octave.
- Hardware location: CLIP page; 12 numbered pads.
- Access and interaction: CLIP mode makes pads 1-12 launch/select slots, with explicit select-versus-launch option. BANK soft key handles bank presets; EDIT ALL and launch quantization remain in header.
- Class: Performance + contextual.
- Feedback: Pads indicate selected, queued, playing and empty using brightness/pulse plus on-screen words.
- Compromise or qualification: Pads share the source selector; mode is conspicuous. Keyboard trigger-octave mode remains available concurrently.

## R29 - Clip editor

- Documentation: [Serum 2 User Guide, pp. 224-233](https://xferrecords.com/manual/serum-2/docs).
- Capability: Full piano roll with polyphonic note pitch/time/duration/velocity, selection and clipboard/time-range operations; grid, zoom/fold, start/end/offset, quantize, chop, legato, reverse, mute, conform to scale and time scaling.
- Hardware location: CLIP/EDIT piano roll.
- Access and interaction: Record or step-enter from the keybed. E1 event, E2 onset, E3 pitch, E4 duration, E5 velocity, E6 zoom. Navigator/multiselect + tool keys expose clipboard, time-range split, quantize/chop/legato/reverse/mute/scale/fold and loop markers.
- Class: Deep editing + optional touch.
- Feedback: Piano roll with note properties, range selection and playhead.
- Compromise or qualification: Fine note editing is less spacious than desktop; full event operations and exact entry remain onboard.

## R30 - Clip recording/output

- Documentation: [Serum 2 User Guide, pp. 237-243](https://xferrecords.com/manual/serum-2/docs).
- Capability: Record keyboard/MIDI performances using overdub or extend; generated MIDI output Off/Clip Player/On; clip into arp then key/scale processing; macro assignment remains available.
- Hardware location: REC/PLAY/STOP and MIDI settings.
- Access and interaction: REC arms chosen clip; choose overdub/extend. Local keybed/external MIDI feed the same record path. MIDI OUT setting chooses Off/Clip-only/processed. DIN and USB destinations selected separately.
- Class: Performance + contextual.
- Feedback: Record armed/recording lamps, committed note color/state, routing monitor and MIDI activity.
- Compromise or qualification: DAW track routing is replaced by physical port routing; a computer is optional.

## R31 - Arpeggiator banks

- Documentation: [Serum 2 User Guide, pp. 244-252,263-266](https://xferrecords.com/manual/serum-2/docs).
- Capability: Arp slots/banks/presets, launch quantization/edit-all/lock and trigger octave; factory shapes plus fully editable custom patterns.
- Hardware location: ARP page; 12 numbered pads.
- Access and interaction: Select/launch arp slots using pads; bank/pattern init/load/save/rename, launch quantization/edit-all and lock are explicit soft actions.
- Class: Performance + contextual.
- Feedback: Arp slot, shape/rate, bank and lock.
- Compromise or qualification: Shared pads have explicit ARP status; no assumption that clips and arps are the same engine.

## R32 - Arp pattern depth

- Documentation: [Serum 2 User Guide, pp. 250-262](https://xferrecords.com/manual/serum-2/docs).
- Capability: Pattern length/modes/random time, step modes, wrap/transpose range, note event editor and automation lanes including accent/strum; shape/rate/shift/range, playback offset/repeats/gate/chance/divide, latch/thru, retrigger and velocity decay/target.
- Hardware location: ARP/EDIT; rate control via E bank.
- Access and interaction: Custom graph is edited with the event controls and lane selector for accent/strum/automation. Named parameter banks retain all shape, wrap, transpose, gate/chance/divide/retrigger/velocity options.
- Class: Contextual + deep editing.
- Feedback: Pattern events and lane graph, live held-note index and range behavior.
- Compromise or qualification: Advanced pattern design needs the display; normal play/latch/launch remains tactile.

## R33 - Keyboard transformation

- Documentation: [Serum 2 User Guide, pp. 267-273](https://xferrecords.com/manual/serum-2/docs).
- Capability: Transpose, key/scale, swing/division, oscillator and arp key/velocity mapping for splits/layers including repeated octave-specific mapping behavior.
- Hardware location: VOICE/Mapping and Scale pages; octave buttons.
- Access and interaction: Select oscillator or arp, hold low/high soft keys while playing endpoints; E controls set exact note and velocity bounds, range move and octave mapping. Key/scale/swing are independent fields.
- Class: Performance + display assisted.
- Feedback: Colored/labeled ranges over all MIDI notes, velocity lanes, transpose and scale status.
- Compromise or qualification: Splits/layers are within one Serum patch architecture, not invented independent multitimbral engines.

## R34 - Wavetable frame editor

- Documentation: [Serum 2 User Guide, pp. 274-277,281-290](https://xferrecords.com/manual/serum-2/docs).
- Capability: All drawing tools, grid, frame selection/reorder/insert/remove/copy/paste/sort, single/all processing, morph operations, import/export/save and dirty-state indication.
- Hardware location: OSC EDIT/Table.
- Access and interaction: Frame navigation and drawing use same six encoders/tool keys; menu explicitly distinguishes selected-frame versus all-frame operations; navigator plus range modifier reorders/selects frames.
- Class: Deep editing.
- Feedback: Thumbnail strip, scope of process, waveform, grid and dirty flag.
- Compromise or qualification: Optional touch makes drawing faster; tool and numeric workflows remain complete without touch.

## R35 - Harmonic editor

- Documentation: [Serum 2 User Guide, pp. 278-280](https://xferrecords.com/manual/serum-2/docs).
- Capability: 512 harmonic amplitude/phase bins, clearing/filtering/generation/randomization/octave/phase processing with exact numerical editing.
- Hardware location: EDIT/Table/FFT.
- Access and interaction: E1 bin index/range, E2 amplitude, E3 phase, E4 process, E5 grid, E6 zoom. Shift selects harmonic ranges; process menu contains all official operations.
- Class: Deep editing + display assisted.
- Feedback: Magnitude and phase plots with selected bin number/value.
- Compromise or qualification: A 7-inch display pages the 512 bins; no limit to first visible bins.

## R36 - Audio/image import

- Documentation: [Serum 2 User Guide, pp. 291-303](https://xferrecords.com/manual/serum-2/docs).
- Capability: Single/multicycle and multiple-file import, zero-snap/dynamic/frequency estimation/fixed-size/FFT methods, numeric/pitch import overrides, sidecar and FolderInfo text overrides, image luminance import, content embedding and missing-file repair.
- Hardware location: FILES/Import; EDIT/Convert; Save/Dependencies.
- Access and interaction: File browser accepts audio/images/multiple single cycles; import method and numeric/pitch overrides selected before commit. Onboard text editor edits sidecar and FolderInfo files. Save offers Embed; missing-file resolver searches USB/internal storage.
- Class: Deep editing.
- Feedback: Import method/preview, file paths and dependency manifest with embedded/linked/missing state.
- Compromise or qualification: OS drag/drop becomes explicit file selection. Image import is an audio function, not decorative artwork on the model.

## R37 - Formula parser

- Documentation: [Serum 2 User Guide, pp. 304-311](https://xferrecords.com/manual/serum-2/docs).
- Capability: Complete documented math functions/operators/constants/variables including x/w/y/z/q/in/sel/rand; single/all-frame or harmonic generation, formula presets and editable user formula files.
- Hardware location: EDIT/Table/Formula.
- Access and interaction: Onboard token-aware text editor and symbol palette; navigator/encoders insert tokens and numeric values; touch keyboard optional. USB HID keyboard is optional for speed. Load/save/edit user formula text files onboard.
- Class: Deep editing.
- Feedback: Expression, parse/error location, single/all-frame or FFT scope and audition before replace.
- Compromise or qualification: Formula entry is slower using knobs; complete syntax remains accessible without external equipment.

## R38 - Voice control

- Documentation: [Serum 2 User Guide, pp. 316-319](https://xferrecords.com/manual/serum-2/docs).
- Capability: Up to eight voice-control steps, oscillator targeting, per-step settings and mod1/mod2, random pan/detune/cutoff/envelopes, envelope/LFO scaling and configuration presets.
- Hardware location: VOICE/Control.
- Access and interaction: Set 1-8 steps, target oscillators and per-step fields via E bank; edit Mod1/2 lanes, random fields and envelope/LFO scaling; load/save configuration.
- Class: Contextual + deep editing.
- Feedback: Eight-step voice table and current voice index; values with units.
- Compromise or qualification: A shared editor replaces permanent per-step hardware.

## R39 - Quality/compatibility

- Documentation: [Serum 2 User Guide, pp. 319-320](https://xferrecords.com/manual/serum-2/docs).
- Capability: Draft 1x, High 2x, Ultra 4x oversampling; smoothing and Serum1 compatibility, quality lock and Ultra offline rendering preference.
- Hardware location: SYSTEM/Quality; Render.
- Access and interaction: Preserve explicit 1x/2x/4x selection and S1 compatibility/smoothing/lock. Offline bounce can request Ultra irrespective of realtime capacity.
- Class: Display assisted.
- Feedback: Quality always in header; load/deadline meter and overload warning; no automatic quality reduction.
- Compromise or qualification: Realtime note capacity depends on benchmark. Full engine settings remain selectable; demanding patches can render offline.

## R40 - Tuning

- Documentation: [Serum 2 User Guide, pp. 320-321](https://xferrecords.com/manual/serum-2/docs).
- Capability: Concert pitch, .tun loading, tuning lock and MTS-ESP integration for shared tuning.
- Hardware location: SYSTEM/Tuning.
- Access and interaction: Concert pitch and .tun import/lock; onboard shared tuning service carries tuning tables. USB session bridge can receive a DAW MTS-ESP table when a computer is connected.
- Class: Display assisted.
- Feedback: Tuning file/service status, pitch reference and last successful synchronization.
- Compromise or qualification: MTS-ESP is an in-process computer API, not raw DIN MIDI. Transparent DAW sharing requires a separately engineered bridge; not asserted to work today.

## R41 - MPE/MIDI

- Documentation: [Serum 2 User Guide, pp. 25-27,314-315,325-326](https://xferrecords.com/manual/serum-2/docs).
- Capability: MPE enable/default, XYZ mappings and pitch range, expression axis polarity, MIDI CC learn/map load/save and preset mapping behavior.
- Hardware location: SYSTEM/MIDI and OTHER expression sources.
- Access and interaction: DIN/USB accept MPE and pressure; native keybed supplies velocity/release velocity/poly pressure. Map XYZ/pitch/CC and save maps; optional USB MPE controller supplies gestures absent on ordinary keys.
- Class: Performance + contextual.
- Feedback: Per-axis input monitor, channel zone, bend range and map name.
- Compromise or qualification: 61-key poly-pressure action does not sense per-key lateral or longitudinal movement. External MPE remains supported, as in software.

## R42 - Preset browser

- Documentation: [Serum 2 User Guide, pp. 18-22,327-339](https://xferrecords.com/manual/serum-2/docs).
- Capability: Folders, search/name/category/tags/ratings, previews including fallback/embedded clip and macro audition, metadata, create/move/rename/delete, database repair, preset pack import/export with metadata/artwork/locks and embedding dependencies.
- Hardware location: BROWSE encoder; six browse soft keys; FILES.
- Access and interaction: Turn BROWSE to list, press to load; preview/stop soft keys; filter categories/tags/rating and search by onboard text entry. Save metadata/pack/dependencies/artwork with file picker; database maintenance in FILES.
- Class: Dedicated + display assisted.
- Feedback: Preset title, dirty/lock/loading status, search results, embedded clip and macro labels.
- Compromise or qualification: Bulk metadata editing is slower; no computer needed. Preloading/set lists are proposed hardware conveniences, not documented Serum features.

## R43 - Editing and preferences

- Documentation: [Serum 2 User Guide, pp. 23-27,312-315,323-326,340-345,349-353](https://xferrecords.com/manual/serum-2/docs).
- Capability: Undo/redo, fine/reset/exact entry, contextual help, module locks/init/copy, render/resample/export, preferences/power-user text files, MIDI/note preset and oscillator-preset stepping, file structure, update/version and shortcuts-equivalent operations.
- Hardware location: UNDO/REDO/SAVE/BACK; SYSTEM/FILES; HELP via hold.
- Access and interaction: Dedicated edit history and save; FINE modifier, exact entry and reset in encoder context. Built-in file/text tools expose preferences, formula and MIDI maps. Render OSC Warp and Resample are explicit OSC operations. Update from USB with rollback.
- Class: Dedicated + deep editing.
- Feedback: Undo action name, save/dependency status, help text, firmware version and update state.
- Compromise or qualification: Computer-only UI size, mouse and host-focus preferences become hardware display/input preferences; synthesis semantics remain.

## R44 - Host-dependent behavior

- Documentation: [Serum 2 User Guide, pp. 18,22,192-193,239-240,315,321](https://xferrecords.com/manual/serum-2/docs).
- Capability: DAW track insertion, drag audio/MIDI to host, host transport/sample position/tempo and DAW-shared tuning need explicit appliance equivalents or declared interoperability limits.
- Hardware location: Internal transport/FILES/USB/Tuning bridge.
- Access and interaction: Internal sample-position clock replaces DAW host transport. MIDI clock/start/stop syncs performance; audio/MIDI drag export becomes save-to-file and USB transfer; plugin insertion is outside an appliance workflow.
- Class: System integration.
- Feedback: Clock source/tempo/transport, export paths and bridge status.
- Compromise or qualification: Exact DAW sample-position/automation and in-process MTS behavior need a host bridge. The standalone engine works without it; desktop integration is a declared engineering gap.

## Coverage audit status

44/44 public-manual capability groups mapped; none deliberately omitted. Host-only operations are translated in R44 and explicit interoperability limitations appear in R40-R44. Authenticated newer-release reconciliation remains open. DSP parity, realtime capacity, tactile usability and engineering certification are not established by this conceptual audit.
