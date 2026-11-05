# The original run's documents

These are the documents the original autonomous run wrote (GPT-6.1 Sol in Codex, one 64-minute session), as it
wrote them: unchanged, except that a local file path was removed from `SERUM_REQUIREMENTS.md`. They describe the
original scene, not the audited revision beside this folder; [the example's README](../README.md) says what the
revision changed.

| File | What it holds |
| --- | --- |
| [SERUM_REQUIREMENTS.md](SERUM_REQUIREMENTS.md) | The manual reduced to 44 capability groups, R01 to R44, each with its page range and the behaviour it requires; written before any geometry |
| [FUNCTION_MAP.md](FUNCTION_MAP.md) | For each group: where it is on the instrument, how it is reached, its class (dedicated, contextual, display-assisted, performance, deep editing), its feedback and its compromise |
| [HARDWARE_ARCHITECTURE.md](HARDWARE_ARCHITECTURE.md) | The compute contract, memory and storage, the audio path and converters, control scanning, I/O, power and cooling, each marked documented, user-supplied, reference-derived or designed |
| [DESIGN_NOTES.md](DESIGN_NOTES.md) | The interface philosophy ("the parameter, not a screen pixel"), the modulation sequence, displays, ergonomics, the reference instruments ("Reference lessons and original identity") and what remains uncertain |
| [assembly_manifest.json](assembly_manifest.json) | The service assemblies and how the rear outputs map to instances |
| [control_rig.json](control_rig.json) | The intended motion of every modelled key and control (the scene animates a representative few) |

Read them with the audit's qualifications:

- The 44 groups and the check that every group is mapped were written by the same agent; nobody has compared the
  inventory with the manual parameter by parameter.
- Each requirement row is a paraphrase of its pages, not a quotation. One detail in R35, the harmonic editor's bin
  count, is not on the pages that row cites; the revision's scene leaves it out.
- `FUNCTION_MAP.md` and `DESIGN_NOTES.md` name FILES, HELP, a Shift key and "tool keys", which the original scene
  did not have. In the revision FILES and SHIFT are keys (hold SHIFT for help) and the six soft keys under the
  display are the tool keys; the "BROWSE encoder" and the "navigator" are one control.
- Paths such as `research/` and `requirements_data.py` name files of the run's own folder, which is not published
  (it holds the manufacturers' manuals and photographs).
