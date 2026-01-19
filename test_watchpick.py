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


if __name__ == "__main__":
    unittest.main()
