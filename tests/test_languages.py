"""The translation tables must be complete and the generated language files must match them."""
import os, sys, tempfile, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ui", "lang"))
import build_lang as bl


class Languages(unittest.TestCase):
    def test_tables_are_complete_and_placeholders_match(self):
        self.assertEqual(bl.check(bl.ROWS_A + bl.ROWS_B + bl.ROWS_M), [])

    def test_no_english_text_is_listed_twice_across_the_parts(self):
        keys = [" ".join(r[0].split()) for r in bl.ROWS_A + bl.ROWS_B + bl.ROWS_M]
        self.assertEqual(len(keys), len(set(keys)))

    def test_generated_files_are_up_to_date(self):
        """If this fails, run: python ui/lang/build_lang.py"""
        windows, phone = bl.ROWS_A + bl.ROWS_B, bl.ROWS_A + bl.ROWS_B + bl.ROWS_M
        with tempfile.TemporaryDirectory() as tmp:
            for folder, rows, live in (("w", windows, os.path.join(ROOT, "ui", "lang")), ("p", phone, os.path.join(ROOT, "mobile", "www", "lang"))):
                bl.write_packs(rows, os.path.join(tmp, folder))
                for code in bl.CODES:
                    fresh = open(os.path.join(tmp, folder, code + ".js"), encoding="utf-8").read()
                    current = open(os.path.join(live, code + ".js"), encoding="utf-8").read()
                    self.assertEqual(fresh.replace("\r\n", "\n"), current.replace("\r\n", "\n"), f"{code} in {live} is stale")
        a = open(os.path.join(ROOT, "ui", "i18n.js"), encoding="utf-8").read()
        b = open(os.path.join(ROOT, "mobile", "www", "i18n.js"), encoding="utf-8").read()
        self.assertEqual(a.replace("\r\n", "\n"), b.replace("\r\n", "\n"), "mobile/www/i18n.js is not a copy of ui/i18n.js")

    def test_every_language_the_app_offers_has_a_file(self):
        for code in bl.CODES:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "ui", "lang", code + ".js")), code)
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "mobile", "www", "lang", code + ".js")), code)


if __name__ == "__main__":
    unittest.main()
