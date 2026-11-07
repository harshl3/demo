import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from catchcheck import build_report, check_catch, main, parse_entry, parse_rules


RULES = parse_rules("cod, 40, 5, 1.5\nhaddock, 30, 2, 0.8\n")


class ParseRulesTests(unittest.TestCase):
    def test_reads_rules_and_skips_comments(self):
        rules = parse_rules("# header\n\nCod, 40, 5, 1.5\r\n")
        self.assertEqual(
            rules,
            {
                "cod": {
                    "min_length": 40.0,
                    "max_per_day": 5,
                    "min_weight": 1.5,
                }
            },
        )

    def test_bad_rules_line_names_the_line(self):
        with self.assertRaisesRegex(ValueError, "rules line 2"):
            parse_rules("cod, 40, 5, 1.5\nhaddock, 30, many, 0.8\n")


class ParseEntryTests(unittest.TestCase):
    def test_valid_entry(self):
        self.assertEqual(parse_entry(" Cod , 41 , 3.2 "), ("cod", 41.0, 3.2))

    def test_rejects_wrong_field_count(self):
        with self.assertRaisesRegex(ValueError, "expected 3 fields"):
            parse_entry("cod, 41")

    def test_rejects_non_positive_and_non_numbers(self):
        for line in ["cod, 0, 3.2", "cod, -4, 3.2", "cod, forty, 3.2", "cod, nan, 3.2"]:
            with self.subTest(line=line):
                with self.assertRaisesRegex(ValueError, "length"):
                    parse_entry(line)
        with self.assertRaisesRegex(ValueError, "weight"):
            parse_entry("cod, 41, -1")


class CheckCatchTests(unittest.TestCase):
    def test_task_example_cod_too_short(self):
        verdicts, totals, rejected = check_catch("cod, 38, 3.0", RULES)
        self.assertEqual(
            verdicts,
            ["line 1: REJECTED – too short (38 cm < 40 cm): cod, 38, 3.0"],
        )
        self.assertEqual(totals, {"cod": 1})
        self.assertEqual(rejected, 1)

    def test_ok_entry(self):
        verdicts, _, rejected = check_catch("cod, 41, 3.2", RULES)
        self.assertEqual(verdicts, ["line 1: OK: cod, 41, 3.2"])
        self.assertEqual(rejected, 0)

    def test_names_every_problem(self):
        verdicts, _, _ = check_catch("cod, 30, 1.0", RULES)
        self.assertIn("too short", verdicts[0])
        self.assertIn("too light", verdicts[0])

    def test_unknown_species(self):
        verdicts, totals, rejected = check_catch("pollock, 50, 2.1", RULES)
        self.assertIn("species unknown", verdicts[0])
        self.assertEqual(totals, {"pollock": 1})
        self.assertEqual(rejected, 1)

    def test_daily_limit_counts_only_kept_fish(self):
        log = "haddock, 35, 1\nhaddock, 20, 1\nhaddock, 37, 1\nhaddock, 36, 1\n"
        verdicts, totals, rejected = check_catch(log, RULES)
        self.assertTrue(verdicts[0].startswith("line 1: OK"))
        self.assertIn("too short", verdicts[1])
        self.assertTrue(verdicts[2].startswith("line 3: OK"))
        self.assertIn("daily limit exceeded (max 2 haddock)", verdicts[3])
        self.assertEqual(totals, {"haddock": 4})
        self.assertEqual(rejected, 2)

    def test_malformed_lines_do_not_crash_and_keep_line_numbers(self):
        log = "# boat\r\n\r\ncod, forty, 2\ncod\ncod, 41, 3.2\n"
        verdicts, totals, rejected = check_catch(log, RULES)
        self.assertEqual(len(verdicts), 3)
        self.assertTrue(verdicts[0].startswith("line 3: MALFORMED"))
        self.assertTrue(verdicts[1].startswith("line 4: MALFORMED"))
        self.assertTrue(verdicts[2].startswith("line 5: OK"))
        self.assertEqual(totals, {"cod": 1})
        self.assertEqual(rejected, 2)


class ReportTests(unittest.TestCase):
    def test_summary_lists_species_and_rejected(self):
        report = build_report(
            "cod, 41, 3.2\ncod, 38, 3.0\nhaddock, 35, 1\n",
            RULES,
        )
        self.assertEqual(
            report,
            "line 1: OK: cod, 41, 3.2\n"
            "line 2: REJECTED – too short (38 cm < 40 cm): cod, 38, 3.0\n"
            "line 3: OK: haddock, 35, 1\n"
            "Summary\n"
            "cod: 2 fish\n"
            "  haddock: 1 fish\n"
            "rejected entries: 1",
        )

    def test_main_reads_files(self):
        with tempfile.TemporaryDirectory() as folder:
            log_path = os.path.join(folder, "log.txt")
            rules_path = os.path.join(folder, "rules.txt")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("cod, 38, 3.0\n")
            with open(rules_path, "w", encoding="utf-8") as handle:
                handle.write("cod, 40, 5, 1.5\n")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main([log_path, rules_path])

            self.assertEqual(code, 0)
            self.assertIn("too short", output.getvalue())
            self.assertIn("rejected entries: 1", output.getvalue())

    def test_main_reports_missing_file(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["no_such_log.txt", "no_such_rules.txt"])
        self.assertEqual(code, 1)
        self.assertIn("cannot read file: no_such_log.txt", output.getvalue())


if __name__ == "__main__":
    unittest.main()
