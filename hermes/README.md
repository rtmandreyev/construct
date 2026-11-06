# hermes/

`construct/` is Construct for Hermes as Hermes installs it:

```bash
hermes plugins install rtmandreyev/construct#hermes/construct
```

It is generated, never edited by hand: the plugin's source is [`hosts/hermes/construct/`](../hosts/hermes/construct/README.md),
and `python3 scripts/hermes_plugin.py` rebuilds this folder from it, adding the bundled engine (`_vendor/`), the
skill's references, the shipped constructs (`examples/`) and three.js. A test fails while it differs from a fresh
build.
