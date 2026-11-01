"""Пакет установки: в нём всё, что нужно установщику, и ничего лишнего."""
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_release  # noqa: E402


class ReleasePackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = build_release.build("0.0.0", cls.dir.name)
        cls.archive = zipfile.ZipFile(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.archive.close()
        cls.dir.cleanup()

    def test_has_translation_and_installer(self):
        names = set(self.archive.namelist())
        for needed in ("translation/Russian/translation.csv",
                       "scripts/install.py", "install.bat", "LICENSE"):
            self.assertIn(needed, names)

    def test_installer_imports_are_packed(self):
        """Каждый модуль scripts/, который импортирует установщик, лежит в пакете."""
        names = set(self.archive.namelist())
        for module in ("patch_assets", "font_merge", "font_metrics",
                       "font_source", "make_pixel_font", "make_smooth_font",
                       "make_ui_pixel_font", "fetch_fonts"):
            self.assertIn("scripts/%s.py" % module, names)

    def test_batch_file_has_crlf(self):
        """cmd.exe не разбирает пакетный файл с одними LF."""
        data = self.archive.read("install.bat")
        self.assertIn(b"\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

    def test_no_game_files_or_work_files(self):
        for name in self.archive.namelist():
            self.assertFalse(name.endswith((".assets", ".exe", ".dll")), name)
            self.assertFalse(name.startswith("work/"), name)


if __name__ == "__main__":
    unittest.main()
