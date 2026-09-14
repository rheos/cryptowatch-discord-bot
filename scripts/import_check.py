#!/usr/bin/env python3
"""Import every module so a dependency bump has to survive the real API.

compileall proves the files parse; it never imports them. Cog classes,
`commands` decorators and `app_commands` definitions all evaluate at import
time, which is exactly where a removed or renamed API in a bumped dependency
shows up. main.py is skipped because importing it would start the bot.
"""

import importlib
import pathlib
import sys

# Running this as `python scripts/import_check.py` puts scripts/ on sys.path,
# not the repo root, so every `import cogs...` would fail for the wrong
# reason. Put the working directory first so the check is about the
# dependencies rather than about how it was invoked.
sys.path.insert(0, str(pathlib.Path.cwd()))

SKIP_NAMES = {"main.py"}


def module_names(root: pathlib.Path) -> list[str]:
    names = []
    for path in sorted(root.rglob("*.py")):
        text = str(path)
        if "__pycache__" in text or path.name in SKIP_NAMES:
            continue
        if path.parts and path.parts[0] == "scripts":
            continue
        names.append(text[:-3].replace("/", "."))
    return names


def main() -> int:
    names = module_names(pathlib.Path("."))
    if not names:
        print("no modules found to import", file=sys.stderr)
        return 1
    failed = 0
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report every failure, not the first
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"imported ok={len(names) - failed} failed={failed} of {len(names)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
