#!/usr/bin/env python3

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SKIP_DIR_NAMES = {".git", "node_modules", "dist", "build", "__pycache__"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_watch_ts() -> Path:
    env = os.environ.get("SUB_WATCH_TS")
    if env:
        return Path(env).expanduser()
    return Path('~/node/sub/src/cli/watch.ts').expanduser()


def _iter_files(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        results: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and d not in SKIP_DIR_NAMES and not d.endswith(".tmp")
            ]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.is_file():
                    results.append(path)
        return results

    return [p for p in root.iterdir() if p.is_file()]


def _normalize_ext(ext: str | None) -> str | None:
    if not ext:
        return None
    return ext if ext.startswith(".") else f".{ext}"


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

    proc = subprocess.run(
        argv,
        input=("\n".join(lines) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None

    selected = proc.stdout.decode("utf-8").rstrip("\n")
    if not selected:
        return None

    if "\t" in selected:
        _, path_str = selected.split("\t", 1)
    else:
        path_str = selected

    return Path(path_str)


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


def _build_watch_argv(
    *,
    watch_ts: Path,
    file_path: Path,
    type_: str,
    no_warn: bool,
    baseline_path: Path | None,
    passthrough: list[str],
) -> list[str]:
    argv: list[str] = ["npx", "tsx", str(watch_ts), str(file_path)]
    argv += ["--type", type_]
    if no_warn:
        argv.append("--no-warn")
    if baseline_path is not None:
        argv += ["--baseline", str(baseline_path)]
    argv += passthrough
    return argv


def _shell_join(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def _copy_text(text: str, copy_cmd: str) -> None:
    argv = shlex.split(copy_cmd)
    subprocess.run(argv, input=(text + "\n").encode("utf-8"), check=True)


@dataclass(frozen=True)
class Config:
    root: Path
    recursive: bool
    ext: str | None
    query: str
    watch_ts: Path
    type_: str
    no_warn: bool
    baseline_root: Path | None
    baseline_override: Path | None
    no_baseline: bool
    copy: bool
    copy_cmd: str
    print_only: bool
    run: bool
    passthrough: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Interactively pick a text file (no need to type Chinese), then run the watch CLI "
            "with a derived baseline path."
        )
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Optional ASCII hint to pre-filter filenames before picking (e.g. '(1)', '2024').",
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("TEXT_ROOT") or ".",
        help="Search root (default: $TEXT_ROOT or current directory).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=False,
        help="Search recursively under --root (default: false).",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_false",
        dest="recursive",
        help="Only search direct children of --root (default).",
    )
    parser.add_argument(
        "--ext",
        default="txt",
        help="File extension filter (default: txt). Use '*' to disable filtering.",
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
    parser.add_argument(
        "--no-warn",
        action="store_true",
        default=True,
        help="Include --no-warn (default: true).",
    )
    parser.add_argument(
        "--warn",
        action="store_false",
        dest="no_warn",
        help="Do not include --no-warn.",
    )
    parser.add_argument(
        "--baseline-root",
        default=os.environ.get("BASELINE_ROOT"),
        help="Derive baseline as <baseline-root>/<stem>.baseline<ext> (default: $BASELINE_ROOT).",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Override baseline path explicitly.",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Omit --baseline entirely.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy the generated command to the clipboard.",
    )
    parser.add_argument(
        "--copy-cmd",
        default="wl-copy",
        help="Clipboard command (default: wl-copy).",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Print the command (default: false).",
    )
    parser.add_argument(
        "--no-run",
        dest="run",
        action="store_false",
        default=True,
        help="Do not execute the command; useful with --print/--copy.",
    )
    args, passthrough = parser.parse_known_args()

    root = Path(args.root).expanduser()
    if not root.exists():
        print(f"error: --root does not exist: {root}", file=sys.stderr)
        return 1

    ext = None if args.ext == "*" else _normalize_ext(args.ext)
    watch_ts = Path(args.watch_ts).expanduser().resolve()
    if not watch_ts.exists():
        print(f"error: watch.ts not found: {watch_ts} (set $SUB_WATCH_TS or --watch-ts)", file=sys.stderr)
        return 1

    baseline_root = Path(args.baseline_root).expanduser().resolve() if args.baseline_root else None
    baseline_override = Path(args.baseline).expanduser().resolve() if args.baseline else None

    config = Config(
        root=root.resolve(),
        recursive=bool(args.recursive),
        ext=ext,
        query=args.query.strip(),
        watch_ts=watch_ts,
        type_=args.type_,
        no_warn=bool(args.no_warn),
        baseline_root=baseline_root,
        baseline_override=baseline_override,
        no_baseline=bool(args.no_baseline),
        copy=bool(args.copy),
        copy_cmd=args.copy_cmd,
        print_only=bool(args.print_only),
        run=bool(args.run),
        passthrough=passthrough[1:] if passthrough[:1] == ["--"] else passthrough,
    )

    files = _iter_files(config.root, recursive=config.recursive)
    if config.ext is not None:
        files = [p for p in files if p.suffix == config.ext]
    if not files:
        print(f"error: no files found under {config.root}", file=sys.stderr)
        return 1

    files = _sort_by_mtime_desc(files)
    if config.query:
        files = [p for p in files if config.query.casefold() in p.name.casefold()]
        if not files:
            print(f"error: no matches for query={config.query!r} under {config.root}", file=sys.stderr)
            return 1

    selected = _pick_with_fzf(files, config.root) or _pick_with_numbered_list(files, config.root)
    if selected is None:
        return 0

    file_path = selected.resolve()
    baseline_path: Path | None
    if config.no_baseline:
        baseline_path = None
    elif config.baseline_override is not None:
        baseline_path = config.baseline_override
    else:
        baseline_path = _default_baseline_for(file_path, config.baseline_root)

    argv = _build_watch_argv(
        watch_ts=config.watch_ts,
        file_path=file_path,
        type_=config.type_,
        no_warn=config.no_warn,
        baseline_path=baseline_path,
        passthrough=config.passthrough,
    )
    command = _shell_join(argv)

    if config.print_only or config.copy or not config.run:
        print(command)

    if config.copy:
        try:
            _copy_text(command, config.copy_cmd)
        except FileNotFoundError:
            print(f"error: copy command not found: {config.copy_cmd}", file=sys.stderr)
            return 3
        except subprocess.CalledProcessError as exc:
            print(f"error: copy failed (exit {exc.returncode}): {config.copy_cmd}", file=sys.stderr)
            return 3

    if config.run:
        return subprocess.run(argv).returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
