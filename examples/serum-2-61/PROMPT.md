**The brief given to GPT-6.1 Sol in Codex for the original run, verbatim below the rule (13,120 characters).**

---

Using the Construct skill, design and build a **masterpiece construct of Serum 2 as a real, standalone, flagship 61-key hardware synthesizer**.

The premise is:

**Imagine Xfer Records and Steve Duda decided to manufacture and sell Serum 2 as hardware. Design the physical instrument they could actually ship.**

This is NOT:

- a MIDI controller for Serum 2
- a computer that merely hosts the existing Serum 2 plugin
- a generic synthesizer inspired by Serum
- an emulation of Serum
- a decorative concept model
- a toy
- a software UI placed on a large touchscreen

It is **Serum 2 itself, realized as a standalone hardware synthesizer**.

Assume the Serum 2 synthesis/DSP architecture can be implemented as native firmware/software on appropriate dedicated computing hardware. Your job is to design the complete physical product around it.

A user should be able to buy this instrument, plug audio/headphones into it, turn it on, and have the complete Serum 2 synthesis system available without a computer.

## Source of truth

Research the **latest official Serum 2 manual/documentation thoroughly before designing anything**.

Build a requirements inventory first.

Treat the documented Serum 2 architecture and functionality as the specification the hardware must implement.

Do not design the front panel first and then squeeze Serum into it.

Work in this order:

**Serum 2 documentation → functional requirements → interaction architecture → hardware architecture → physical layout → industrial design → Construct**

For every major Serum 2 capability, determine how it exists on the physical instrument.

Do not silently remove difficult features.

If something cannot reasonably receive a dedicated physical control, design a coherent contextual/display-assisted interaction for it.

## Product goal

Design a **premium full-size 61-key flagship synthesizer** that could plausibly be sold as the hardware version of Serum 2.

It should preserve Serum's depth while taking advantage of physical hardware.

The goal is not to reproduce Serum's software interface literally.

Ask instead:

> If Serum had always been a hardware instrument, what would its interface have become?

Common synthesis actions should be immediate and tactile.

Deep functionality can use contextual controls and displays, but the instrument should not become a touchscreen with a keyboard attached.

The result must be understandable as an instrument.

## Design references

Research these instruments for industrial-design and interaction lessons:

- Frap Tools Magnolia
- UDO Super 6
- Modal Electronics 002
- Alesis Andromeda A6

Study things such as:

- control density
- ergonomics
- panel hierarchy
- premium materials
- keyboard-to-panel proportions
- grouping
- tactile controls
- display integration
- performance interaction
- how complex synthesis architectures are made physically understandable

**Do not copy any of them.**

Do not reproduce their panel layouts, silhouettes, distinctive control arrangements, colors or visual identities.

Borrow reasoning, not appearance.

The final product must have an original identity appropriate to Serum.

## Visual identity

Premium, futuristic and unapologetically technological.

A slight science-fiction quality is welcome, but it must look like a real high-end musical instrument that could be manufactured.

Avoid:

- gamer RGB
- generic cyberpunk decoration
- meaningless illuminated lines
- movie-prop controls
- toy-like proportions
- excessive visual noise
- giant touchscreen dependence

Lighting should communicate useful state such as modulation, routing, selection or activity.

Materials can include machined/anodized metal, high-quality polymers, glass and other plausible premium materials.

## Physical format

Full-size **61-key keyboard**.

Research realistic dimensions and ergonomics for premium 61-key synthesizers.

Include a complete product, not merely the top panel:

- keyboard and keybed
- performance controls
- top/control panel
- displays
- rear I/O
- audio outputs
- headphone output
- MIDI
- USB
- pedal/control inputs
- power
- appropriate data/storage connectivity
- chassis
- underside
- feet
- ventilation/cooling where required
- service/access considerations where plausible

## Translate Serum 2 into hardware

This is the central design problem.

Map Serum 2's documented architecture into physical interaction.

Classify functionality into:

1. **dedicated controls**
2. **shared/contextual controls**
3. **display-assisted controls**
4. **performance controls**
5. **deep-editing pages**

Do not give every parameter a knob.

Do not hide everything in menus either.

Find a coherent balance.

Research the current manual to determine the actual architecture rather than relying on memory.

The physical panel should communicate Serum's signal flow and modulation architecture wherever possible.

## Modulation

Treat modulation as a first-class hardware-design problem.

Serum's modulation workflow is central to the instrument.

Design a physical system that makes it fast to:

- choose a modulation source
- choose a destination
- assign it
- set depth and polarity
- see existing modulation
- see multiple modulators affecting one destination
- edit documented modulation curves/behavior
- remove or reassign modulation
- understand modulation while performing

Possible mechanisms include encoders with illuminated rings, contextual displays, source-selection controls, destination modes or other original solutions.

Do not simply recreate mouse drag-and-drop on a touchscreen.

The physical interaction should feel better because it is hardware.

## Displays

Use displays deliberately.

A high-resolution central display is appropriate where Serum genuinely benefits from visual information, such as:

- wavetable/spectral editing
- waveform visualization
- modulation
- routing
- sequencing
- effects
- preset browsing

Additional contextual displays are allowed if justified.

Do not make touch the primary interaction unless a specific function genuinely benefits from it.

## Hardware architecture

This must not be an empty shell.

Design plausible internal hardware capable of implementing a standalone flagship Serum 2.

Research contemporary synthesizer/workstation hardware architecture and estimate appropriate requirements.

The construct should include meaningful internal components/volumes such as, where justified:

- main compute/DSP board
- CPU/DSP/SoC or other appropriate processing architecture
- RAM
- nonvolatile storage
- audio converters
- analog audio/output circuitry
- headphone amplification
- MIDI/USB/interface electronics
- display/control electronics
- keybed scanning/control hardware
- power supply
- internal buses/cabling
- thermal solution if required
- I/O board(s)

Do not invent exact chip specifications without evidence.

Where the exact compute requirement cannot be established from public Serum documentation, mark the requirement/design as inferred or designed.

The purpose is **physical and architectural plausibility**, not pretending to have Xfer's source code or profiling data.

There must be enough internal physical volume for the electronics you design.

Rear I/O must correspond to plausible internal hardware.

Cooling/ventilation must correspond to the estimated compute and power architecture.

## What "fully functional" means

The finished design should plausibly support the **complete documented current Serum 2 feature set**.

Before finalizing, audit the design against the manual.

For every major Serum subsystem/capability, answer:

- What does it do in Serum 2?
- Where is it on this instrument?
- How does the player access it?
- Is the interaction dedicated, contextual or display-based?
- What visual feedback exists?
- Is anything compromised compared with software?
- If so, why?

Do not call the design complete until this audit is done.

## Physical controls

Every major visible control should have a purpose.

Model important controls as named semantic parts.

Where appropriate include real articulations for:

- knobs/encoders
- faders
- buttons
- switches
- performance controls
- keyboard keys
- adjustable/hinged elements

Controls must be realistically sized and spaced for human hands.

Do not fill unused panel space with fake controls.

## Ergonomics

Evaluate the instrument from a player's perspective.

Ask:

- Can common sound-design operations be performed quickly?
- Can important controls be reached while playing?
- Is the architecture readable at a glance?
- Can modulation be understood without menu archaeology?
- Can a patch be built from init without living inside the display?
- Can extremely complex Serum patches still be edited?
- Can presets be browsed quickly?
- Can it work on stage?
- Are labels and displays readable at normal distance?
- Is control density physically plausible?
- Are frequently paired controls physically near each other?

## Provenance

Use Construct's provenance system aggressively.

Distinguish:

### Verified/documented
Capabilities and behavior explicitly documented in the current official Serum 2 documentation.

### User-supplied
Requirements from this brief, such as:

- standalone hardware Serum 2
- 61 keys
- flagship/premium positioning
- complete documented functionality
- reference instruments
- design direction

### Reference-derived
Dimensions/ergonomic principles/engineering reasoning taken from published information about real synthesizers or electronics.

### Designed/inferred
The new instrument's:

- industrial design
- panel layout
- interaction solutions
- internal electronics architecture where Xfer's requirements are unknown
- chassis
- control assignments
- cooling
- physical construction

Do not blur these categories.

One of the goals of the experiment is to see exactly where documented software requirements stop and product-design invention begins.

## Construct structure

Build the synthesizer from meaningful named parts and subassemblies.

Use a plausible hierarchy such as:

- chassis
- keybed assembly
- performance-control assembly
- control-panel structure
- synthesis control groups
- displays
- encoder/button/fader assemblies
- rear I/O
- compute/electronics bay
- audio electronics
- power
- cooling
- structural supports
- side/end structures
- underside/feet

Use sensible assembly stages.

This should be a product that could conceptually be disassembled and serviced, not a monolithic visual shell.

## Views

Include at minimum:

1. full hero view
2. normal player's view
3. top/control-panel view
4. synthesis/oscillator section close-up
5. modulation workflow close-up
6. effects/sequencing or other deep Serum section
7. rear I/O
8. internal/electronics view

Add views if needed.

## Deliverables

Deliver:

1. final masterpiece Construct
2. scene source
3. glTF for Blender
4. short review film
5. `SERUM_REQUIREMENTS.md`
6. `FUNCTION_MAP.md`
7. `HARDWARE_ARCHITECTURE.md`
8. `DESIGN_NOTES.md`

### SERUM_REQUIREMENTS.md

Inventory the major documented Serum 2 capabilities and cite the documentation.

### FUNCTION_MAP.md

For each major Serum 2 subsystem/capability:

- documentation source
- hardware location
- physical interaction
- dedicated/contextual/display-based
- feedback to the player
- compromise, if any

### HARDWARE_ARCHITECTURE.md

Describe:

- compute architecture
- memory/storage
- audio path
- converters
- control scanning
- display/control electronics
- I/O
- power
- cooling
- internal physical organization
- what is evidence-based versus estimated/designed

Do not claim that a particular processor can run Serum 2 unless evidence supports that conclusion.

Instead specify the performance requirement or class of hardware where exact requirements are unavailable.

### DESIGN_NOTES.md

Explain:

- overall interface philosophy
- how Serum's software architecture became physical
- modulation interaction
- display strategy
- control hierarchy
- ergonomic decisions
- how the reference synthesizers informed reasoning without being copied
- what remains speculative
- what would require actual electrical/mechanical engineering before manufacture

## Quality target

This is a flagship Construct experiment.

Use **masterpiece mode** with the most capable model available.

Take all normal critic rounds seriously.

Prioritize:

1. fidelity to Serum 2's documented functionality
2. coherent hardware interaction
3. ergonomic plausibility
4. plausible internal hardware architecture
5. original industrial design
6. manufacturable-looking physical construction
7. clear interface hierarchy
8. visual quality

A beautiful synthesizer that only exposes half of Serum is a failure.

A complete Serum interface that becomes an unusable wall of tiny controls is also a failure.

A giant touchscreen running something resembling the plugin is a failure.

The target is:

**the instrument Serum 2 might have been if it had been designed from the beginning as a flagship hardware synthesizer.**

Don't rewrite existing files in the folder but create a new one inside the directory for this project where you will work. 
