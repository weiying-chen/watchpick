# Repository Guidelines

## Project Structure

- `watchpick.py`: single-file CLI for interactively selecting a text file and running a `watch.ts` script via `npx tsx`.
- No package layout, tests, or assets directories are currently present; keep changes minimal and self-contained.

## Build, Test, and Development Commands

- Help/usage: `python3 watchpick.py --help`
- Run (interactive pick): `python3 watchpick.py "(1)" --root . --recursive`
- Print only (don’t execute): `python3 watchpick.py --print --no-run`
- Clipboard copy (Wayland default): `python3 watchpick.py --print --no-run --copy` (uses `wl-copy`; override via `--copy-cmd`)

External tools/inputs:
- `fzf` (optional): used for interactive picking; falls back to a numbered list when missing.
- `npx`, `tsx`: required to execute `watch.ts`.
- `SUB_WATCH_TS`: path to `watch.ts` (defaults to `~/node/sub/src/cli/watch.ts`); override with `--watch-ts`.
- `TEXT_ROOT`, `BASELINE_ROOT`: optional defaults for `--root` and `--baseline-root`.

## Coding Style & Naming Conventions

- Python 3.10+ required (uses `str | None` and `list[...]` typing).
- 4-space indentation, type hints preferred, and `pathlib.Path` for filesystem paths.
- Keep functions small and focused; use `_private_helper` naming for internal helpers.

## Testing Guidelines

- No automated tests are included. For changes, do a quick manual check:
  - `python3 -m compileall watchpick.py`
  - `python3 watchpick.py --help`
  - Run with `--print --no-run` to validate command construction without executing `npx`.

## Commit & Pull Request Guidelines

- This directory is not currently a Git repository, so there is no commit-message history to follow.
- Recommended convention if you initialize Git: imperative subject lines (e.g., `Add --no-baseline flag`), small focused commits, and PRs that describe behavior changes and include example commands/output.

## Configuration & Safety Notes

- Paths are resolved and validated; prefer adding new options via `argparse` with clear `--help` text.
- Avoid running destructive shell commands; keep defaults safe and require explicit flags for behavior changes.
