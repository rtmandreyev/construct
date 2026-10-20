"""The product's identity, in one place.

Construct: holographic constructs any agent can build — from a description, honestly.

NAME is the skill, MCP server and command name; DIST the Python distribution; the import
package is this folder (construct_hologram), found from the folder by the entry points. The
contract and format ids version the documents agents write and apps read; the LEGACY ids
(from the toolkit's first home in Tessera) are still accepted for one release.
"""

NAME = "construct"                       # skill, MCP server and command name
TITLE = "Construct"                      # the product, in prose
DIST = "construct-hologram"              # the Python distribution (PyPI "construct" is another project)
TAGLINE = "Holographic constructs any agent can build — from a description, honestly."
VERSION = "0.2.1"
LICENSE = "MIT"
AUTHORS = "The Construct authors"
REPO = "https://github.com/rtmandreyev/construct"

CONTRACT = "construct/0.2"
SCENE_FORMAT = "construct-scene"         # version 2
GEOMETRY_FORMAT = "construct-geometry"   # version 2
PARAMS_FORMAT = "construct-params"       # version 1

# accepted for one release (0.2.x), written by nothing
LEGACY_CONTRACT = "tessera.hologram/0.2"
LEGACY_SCENE_FORMAT = "tessera-hologram"
LEGACY_GEOMETRY_FORMAT = "tessera-hologram-geometry"
LEGACY_PARAMS_FORMAT = "tessera-hologram-params"
