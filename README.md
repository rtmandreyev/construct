# Tessera Hologram Toolkit 0.1.0

Independent Apache-2.0 prototype: deterministic construction sheets, geometry compiler,
CLI, local MCP stdio server and an agent skill. Python 3.10+; standard library only.
No model, account, network service or package installation is required. This is a
working local tool package, not a published or certified Hermes/Claude plugin.

## Use

From any directory, replace `/path/to` with the actual toolkit location:

```sh
python3 /path/to/hologram/cli.py template cd --output cd.json
python3 /path/to/hologram/cli.py validate cd.json
python3 /path/to/hologram/cli.py compile cd.json --output geometry.json
```

In the Tessera repository the directory is `tools/hologram`; module invocation
`python3 -m tools.hologram ...` also works from the repository root. Output files
refuse overwrite unless `--force` is explicit. Validate local artwork bytes with
`--asset-root /path/to/assets` on validate/compile; no download or image decoder
is included. The default validates asset declarations without reading bytes.

## Connect to an MCP host

Launch `python3 /absolute/path/to/hologram/server.py` as a **stdio** server.
For clients accepting the usual `mcpServers` structure, adapt this example to
their documented configuration location (this package does not modify it):

```json
{"mcpServers":{"tessera-hologram":{"command":"/absolute/path/to/python3","args":["/absolute/path/to/hologram/server.py"]}}}
```

Tools: `hologram_template`, `hologram_validate`, `hologram_compile`. They only
operate on JSON supplied in the request: no file access, shell, model calls or
networking. CLI file access is separate. Newline-delimited JSON-RPC uses MCP
protocol version 2025-11-25. Initialization, tool discovery and calls are tested
with a protocol client; actual Hermes/Claude host compatibility is still a gate.
Keep stdout reserved for protocol messages. No API key belongs in this server.

The model runs in the host chosen by the user. A capable model can author sheets;
quality varies, and no claim is made that every LLM will produce valid or accurate
objects. The compiler is deterministic and rejects malformed sheets. The skill
at `skills/create-hologram/SKILL.md` provides a portable authoring workflow.

## Contract

See `schema.json`, the examples and the skill's contract reference. Preserve
facts and their sources separately from inferred geometry and decorative motion.
Verified geometry requires a source. Generic templates are illustrative; the CD
template is a generic jewel case, never an identification of a physical edition.
The compiler carries a canonical source-sheet hash, facts and per-part provenance.
Applications must retain the actual source sheet too; a hash cannot reconstruct it.

Artwork declarations require an asset ID, relative path, SHA-256, media type and
rights statement. A hash and a rights string are declarations, not proof of rights.
Artwork binds to a box front face and compiles to UV quads. The atlas study currently
renders line geometry only; texture display/decoding remains future integration.
No generated approximation may be presented as the authentic album cover.

Budgets: 1 MiB input, 4 MiB output, 128 parts, 128 scalar facts, 32 assets,
20,000 compiled segments; staged assembly at most 5 seconds. No shader source,
script, executable payload, remote URL fetch, or filesystem path outside an explicit
asset root. The implementation validator is authoritative for cross-field rules.

## Verify

From the repository root: `python3 -m unittest tools.hologram.test_hologram
tools.catalog.test_catalog_csv tools.test_tool_regressions`. For a standalone
toolkit, run `python3 -m unittest hologram.test_hologram` from its containing
directory. Only synthetic examples and fixtures are distributed.
