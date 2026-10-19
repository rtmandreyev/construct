"""The product's identity, in one place.

To rename the product: change NAME and TITLE here, `name` in ../pyproject.toml, and rename
this folder (the Python import name; code finds it from the folder, nothing else hard-codes
it). `python3 scripts/rename.py <new-name>` does all three. The contract and format ids
(CONTRACT, "tessera-hologram*") are separate: they change only with a new contract version.
"""

NAME = "hologram-studio"          # the product and skill name (lowercase, hyphenated)
TITLE = "Hologram Studio"         # how it is written in prose
VERSION = "0.2.0"
LICENSE = "MIT"
AUTHORS = "The %s authors" % NAME
CONTRACT = "tessera.hologram/0.2"
