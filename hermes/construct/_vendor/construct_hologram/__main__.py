"""Command line for Construct (see ../README.md)."""

import argparse
import json
import os
import sys
import tempfile

from . import hologram, product, studio


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


class Parser(argparse.ArgumentParser):
    """Construct's parser: an option is only ever its whole name. Prefixes (`--ou` for `--out`) are refused, here and
    in every subcommand's parser (they are made from this class), so a check that reads flags by name holds."""

    def __init__(self, *args, **kwargs):
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)


def build_parser():
    """The whole command line, every subcommand, without running anything."""
    parser = Parser(prog=product.NAME)
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

    studio.add_commands(sub)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command in studio.COMMANDS:
        try:
            return studio.run(args)
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError) as exc:
            # a file named on the command line that is not there or cannot be opened: say which, never a traceback
            sys.stderr.write("%s: cannot read %s: %s\n" % (args.command, exc.filename or "a file", exc.strerror or exc))
            return 1
        except RecursionError:
            sys.stderr.write("%s: a file is nested too deeply to read (thousands of brackets inside each other)\n"
                             % args.command)
            return 1

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
