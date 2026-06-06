#!/usr/bin/env python3

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _default_watch_ts() -> Path:
    env = os.environ.get("SUB_WATCH_TS")
    if env:
        return Path(env).expanduser()
    return Path('~/node/sub/src/cli/watch.ts').expanduser()


def _iter_files(root: Path) -> list[Path]:
    return [p for p in root.iterdir() if p.is_file()]


def _sort_by_mtime_desc(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def _rel_display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _pick_with_fzf(paths: list[Path], root: Path) -> Path | None:
    fzf = shutil.which("fzf")
    if not fzf:
        return None

    lines: list[str] = []
    for path in paths:
        display = _rel_display(path, root)
        lines.append(f"{display}\t{path}")

    argv = [
        fzf,
        "--delimiter=\t",
        "--with-nth=1",
        "--nth=1",
        "--prompt=watch> ",
        "--preview",
        "sed -n '1,60p' {2}",
        "--preview-window=right:60%:wrap",
        "--cycle",
    ]

    selection_path = Path(
        tempfile.NamedTemporaryFile(prefix="watchpick-fzf-", delete=False).name
    )
    bind = (
        "enter:execute-silent("
        f"echo -n {{2}} > {shlex.quote(str(selection_path))}"
        ")+abort"
    )
    argv.append(f"--bind={bind}")

    try:
        proc = subprocess.run(
            argv,
            input=("\n".join(lines) + "\n").encode("utf-8"),
        )
        selected = _resolve_fzf_selection(selection_path, proc.returncode)
    finally:
        try:
            selection_path.unlink()
        except FileNotFoundError:
            pass

    if selected:
        return selected
    return None


def _resolve_fzf_selection(selection_path: Path, returncode: int) -> Path | None:
    selected = selection_path.read_text(encoding="utf-8").strip()
    if selected:
        return Path(selected)
    if returncode != 0:
        return None
    return None


def _pick_with_numbered_list(paths: list[Path], root: Path) -> Path | None:
    shown = paths[:50]
    for i, path in enumerate(shown, start=1):
        print(f"{i:>2}. {_rel_display(path, root)}", file=sys.stderr)
    print("Select a file by number (empty to cancel): ", end="", file=sys.stderr, flush=True)
    choice = sys.stdin.readline().strip()
    if not choice:
        return None
    try:
        index = int(choice)
    except ValueError:
        print("error: please enter a number", file=sys.stderr)
        return None
    if index < 1 or index > len(shown):
        print(f"error: please enter 1..{len(shown)}", file=sys.stderr)
        return None
    return shown[index - 1]


def _default_baseline_for(file_path: Path, baseline_root: Path | None) -> Path:
    name = f"{file_path.stem}.baseline{file_path.suffix}"
    if baseline_root is not None:
        return baseline_root / name
    return file_path.with_name(name)


def _is_baseline_file(path: Path) -> bool:
    return path.stem.endswith(".baseline")


def _sibling_baseline_for(file_path: Path) -> Path:
    return file_path.with_name(f"{file_path.stem}.baseline{file_path.suffix}")


def _filter_files_with_baseline(paths: list[Path]) -> list[Path]:
    return [p for p in paths if not _is_baseline_file(p) and _sibling_baseline_for(p).exists()]


def _build_watch_argv(
    *,
    watch_ts: Path,
    file_path: Path,
    type_: str,
    no_warn: bool,
    baseline_path: Path | None,
    max_cps: int | None,
    min_cps: int | None,
    passthrough: list[str],
) -> list[str]:
    argv: list[str] = ["npx", "tsx", str(watch_ts), str(file_path)]
    argv += ["--type", type_]
    if no_warn:
        argv.append("--no-warn")

    if baseline_path is not None:
        argv += ["--baseline", str(baseline_path)]
    if max_cps is not None:
        argv += ["--max-cps", str(max_cps)]
    if min_cps is not None:
        argv += ["--min-cps", str(min_cps)]
    argv += passthrough
    return argv


def _watch_workdir_from_watch_ts(watch_ts: Path) -> Path:
    # Standard layout: <repo>/src/cli/watch.ts
    if (
        watch_ts.name == "watch.ts"
        and watch_ts.parent.name == "cli"
        and watch_ts.parent.parent.name == "src"
    ):
        return watch_ts.parent.parent.parent
    return watch_ts.parent
@dataclass(frozen=True)
class Config:
    root: Path
    watch_ts: Path
    type_: str
    passthrough: list[str]


def _filter_picker_files(paths: list[Path], type_: str) -> list[Path]:
    if type_ == "subs":
        visible = [p for p in paths if not _is_baseline_file(p)]
        return _filter_files_with_baseline(visible)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Interactively pick a text file, then run the watch CLI."
        )
    )
    parser.add_argument(
        "--watch-ts",
        default=str(_default_watch_ts()),
        help="Path to watch.ts (default: $SUB_WATCH_TS or <repo>/src/cli/watch.ts).",
    )
    parser.add_argument(
        "--type",
        dest="type_",
        default="subs",
        help="Value for --type (default: subs).",
    )
    args, passthrough = parser.parse_known_args()

    root = Path(os.environ.get("TEXT_ROOT") or ".").expanduser()
    if not root.exists():
        print(f"error: TEXT_ROOT does not exist: {root}", file=sys.stderr)
        return 1

    watch_ts = Path(args.watch_ts).expanduser().resolve()
    if not watch_ts.exists():
        print(f"error: watch.ts not found: {watch_ts} (set $SUB_WATCH_TS or --watch-ts)", file=sys.stderr)
        return 1

    config = Config(
        root=root.resolve(),
        watch_ts=watch_ts,
        type_=args.type_,
        passthrough=passthrough[1:] if passthrough[:1] == ["--"] else passthrough,
    )

    files = _iter_files(config.root)
    files = [p for p in files if p.suffix == ".txt"]
    files = _filter_picker_files(files, config.type_)
    if not files:
        print(f"error: no files found under {config.root}", file=sys.stderr)
        return 1

    files = _sort_by_mtime_desc(files)

    if shutil.which("fzf"):
        selected = _pick_with_fzf(files, config.root)
        if selected is None:
            return 0
    else:
        selected = _pick_with_numbered_list(files, config.root)
        if selected is None:
            return 0

    file_path = selected.resolve()
    baseline_path = _default_baseline_for(file_path, None) if config.type_ == "subs" else None

    argv = _build_watch_argv(
        watch_ts=config.watch_ts,
        file_path=file_path,
        type_=config.type_,
        no_warn=False,
        baseline_path=baseline_path,
        max_cps=None,
        min_cps=None,
        passthrough=config.passthrough,
    )

    try:
        workdir = _watch_workdir_from_watch_ts(config.watch_ts)
        return subprocess.run(argv, cwd=workdir).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
