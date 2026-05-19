import tempfile
import unittest
from pathlib import Path

import watchpick


class ResolveFzfSelectionTests(unittest.TestCase):
    def test_returns_selection_even_on_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            selection_path = Path(tempdir) / "selection.txt"
            selection_path.write_text("/tmp/example.txt", encoding="utf-8")
            selected = watchpick._resolve_fzf_selection(selection_path, returncode=1)
            self.assertEqual(selected, Path("/tmp/example.txt"))

    def test_empty_selection_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            selection_path = Path(tempdir) / "selection.txt"
            selection_path.write_text("", encoding="utf-8")
            selected = watchpick._resolve_fzf_selection(selection_path, returncode=0)
            self.assertIsNone(selected)


class BuildWatchArgvTests(unittest.TestCase):
    def test_includes_max_and_min_cps_when_provided(self) -> None:
        argv = watchpick._build_watch_argv(
            watch_ts=Path("/tmp/watch.ts"),
            file_path=Path("/tmp/input.txt"),
            type_="subs",
            no_warn=False,
            baseline_path=Path("/tmp/input.baseline.txt"),
            max_cps=16,
            min_cps=6,
            passthrough=[],
        )
        self.assertIn("--max-cps", argv)
        self.assertIn("16", argv)
        self.assertIn("--min-cps", argv)
        self.assertIn("6", argv)

    def test_does_not_include_cps_flags_when_not_provided(self) -> None:
        argv = watchpick._build_watch_argv(
            watch_ts=Path("/tmp/watch.ts"),
            file_path=Path("/tmp/input.txt"),
            type_="subs",
            no_warn=False,
            baseline_path=Path("/tmp/input.baseline.txt"),
            max_cps=None,
            min_cps=None,
            passthrough=[],
        )
        self.assertNotIn("--max-cps", argv)
        self.assertNotIn("--min-cps", argv)


if __name__ == "__main__":
    unittest.main()
