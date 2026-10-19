"""CLI entrypoint for tessera-hologram."""

import argparse
import json
import os
import sys
import tempfile

from . import hologram


def _emit(obj):
    sys.stdout.write(json.dumps(obj, indent=2) + "\n")


def _write_output(path, obj, force):
    data = json.dumps(obj, indent=2) + "\n"
    if len(data.encode("utf-8")) > hologram.MAX_OUTPUT_BYTES:
        raise hologram.SheetError("output exceeds %d bytes" % hologram.MAX_OUTPUT_BYTES)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".hologram-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        if force:
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path)
            except FileExistsError:
                raise hologram.SheetError("output exists; use --force to overwrite")
            except OSError:
                # Filesystem without hardlinks: fall back to exclusive create.
                try:
                    with open(path, "x", encoding="utf-8") as fh:
                        fh.write(data)
                except FileExistsError:
                    raise hologram.SheetError("output exists; use --force to overwrite")
            os.unlink(tmp)
            tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hologram")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tpl = sub.add_parser("template")
    p_tpl.add_argument("kind")
    p_tpl.add_argument("--title")
    p_tpl.add_argument("--output")
    p_tpl.add_argument("--force", action="store_true")

    p_val = sub.add_parser("validate")
    p_val.add_argument("sheet")
    p_val.add_argument("--asset-root")

    p_cmp = sub.add_parser("compile")
    p_cmp.add_argument("sheet")
    p_cmp.add_argument("--output")
    p_cmp.add_argument("--asset-root")
    p_cmp.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "template":
            sheet = hologram.template(args.kind, args.title)
            if args.output:
                _write_output(args.output, sheet, args.force)
            else:
                _emit(sheet)
            return 0

        sheet = hologram.read_sheet(args.sheet)
        errors = hologram.validate(sheet)
        if args.asset_root and not errors:
            errors = hologram.verify_assets(sheet, args.asset_root)
        if errors:
            _emit({"valid": False, "errors": errors})
            return 1
        if args.command == "validate":
            _emit({"valid": True, "errors": []})
            return 0
        compiled = hologram.compile_sheet(sheet)
        if args.output:
            _write_output(args.output, compiled, args.force)
        else:
            _emit(compiled)
        return 0
    except hologram.SheetError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except OSError as exc:
        sys.stderr.write("error: %s\n" % exc.__class__.__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
