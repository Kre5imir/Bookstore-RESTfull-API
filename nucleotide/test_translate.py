"""Tests for DNA and RNA translation."""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from pathlib import Path

from nucleotide.translate import TranslationError, clean_sequence, main, translate

SCRIPT = Path(__file__).resolve().parent / "translate.py"


class TranslateFunctionTests(unittest.TestCase):
    def test_dna_codons(self):
        protein, leftover = translate("ATGGCTTCAAAATAG")
        self.assertEqual(protein, "MASK")
        self.assertEqual(leftover, 0)

    def test_rna_matches_dna(self):
        dna, _ = translate("ATGGCTTCAAAATAG")
        rna, leftover = translate("AUGGCUUCAAAAUAG")
        self.assertEqual(rna, dna)
        self.assertEqual(rna, "MASK")
        self.assertEqual(leftover, 0)

    def test_lowercase_and_whitespace(self):
        protein, leftover = translate("  atg gcc\nTAA")
        self.assertEqual(protein, "MA")
        self.assertEqual(leftover, 0)

    def test_frames(self):
        sequence = "AATGGCTTCA"
        self.assertEqual(translate(sequence, frame=1), ("NGF", 1))
        self.assertEqual(translate(sequence, frame=2), ("MAS", 0))
        self.assertEqual(translate(sequence, frame=3), ("WL", 2))

    def test_frame_defaults_to_one(self):
        self.assertEqual(translate("ATGGCC"), translate("ATGGCC", frame=1))

    def test_early_stop(self):
        protein, leftover = translate("ATGTAATGG")
        self.assertEqual(protein, "M")
        self.assertEqual(leftover, 0)

    def test_each_stop_codon_ends_translation(self):
        self.assertEqual(translate("ATGTAACCC")[0], "M")
        self.assertEqual(translate("ATGTAGCCC")[0], "M")
        self.assertEqual(translate("ATGTGACCC")[0], "M")
        self.assertEqual(translate("AUGUAACCC")[0], "M")
        self.assertEqual(translate("AUGUAGCCC")[0], "M")
        self.assertEqual(translate("AUGUGACCC")[0], "M")

    def test_through_stops_marks_stars(self):
        protein, leftover = translate("ATGTAATGG", through_stops=True)
        self.assertEqual(protein, "M*W")
        self.assertEqual(leftover, 0)

    def test_through_stops_keeps_every_stop(self):
        protein, _ = translate("ATGTAATAG", through_stops=True)
        self.assertEqual(protein, "M**")

    def test_leftover_bases_still_return_protein(self):
        protein, leftover = translate("ATGCC")
        self.assertEqual(protein, "M")
        self.assertEqual(leftover, 2)

    def test_invalid_character(self):
        with self.assertRaisesRegex(TranslationError, "invalid character 'X' at position 4"):
            translate("ATGX")

    def test_invalid_character_position_ignores_whitespace(self):
        with self.assertRaisesRegex(TranslationError, "position 4"):
            clean_sequence("AT G X")

    def test_mixed_dna_and_rna(self):
        with self.assertRaisesRegex(TranslationError, "both T and U"):
            translate("ATGU")

    def test_invalid_frame(self):
        with self.assertRaisesRegex(TranslationError, "frame must be 1, 2, or 3"):
            translate("ATG", frame=0)

    def test_sequence_shorter_than_frame_offset(self):
        self.assertEqual(translate("AC", frame=3), ("", 0))


class TranslateCliTests(unittest.TestCase):
    def test_argument_and_default_frame(self):
        code, stdout, stderr = _run_main(["ATGCCCAAATAG"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "MPK\n")
        self.assertEqual(stderr, "")

    def test_frame_flag(self):
        code, stdout, stderr = _run_main(["--frame", "2", "AATGGC"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "M\n")
        self.assertEqual(stderr, "note: 2 leftover bases in frame 2 were not translated\n")

    def test_through_stops_flag(self):
        code, stdout, stderr = _run_main(["--through-stops", "ATGTAATAG"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "M**\n")
        self.assertEqual(stderr, "")

    def test_stdin_when_argument_omitted(self):
        code, stdout, stderr = _run_main([], stdin=io.StringIO("AUGGCC\n"))
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "MA\n")
        self.assertEqual(stderr, "")

    def test_leftover_note_for_one_base(self):
        code, stdout, stderr = _run_main(["ATGCCCT"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "MP\n")
        self.assertEqual(stderr, "note: 1 leftover base in frame 1 was not translated\n")

    def test_invalid_input_exits_with_error(self):
        code, stdout, stderr = _run_main(["ATGXCC"])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("error: invalid character 'X' at position 4", stderr)

    def test_missing_sequence_on_a_terminal(self):
        code, stdout, stderr = _run_main([], stdin=_TTY())
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("provide a nucleotide sequence", stderr)

    def test_script_dna_example(self):
        result = _run_script(["ATGGCTTCAAAATAG"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "MASK\n")
        self.assertEqual(result.stderr, "")

    def test_script_rna_frame_and_stops(self):
        framed = _run_script(["--frame", "3", "AAATGGCTTCA"])
        self.assertEqual(framed.returncode, 0)
        self.assertEqual(framed.stdout, "MAS\n")
        self.assertEqual(framed.stderr, "")

        stopped = _run_script(["--through-stops"], stdin_text="AUG UAA UGG")
        self.assertEqual(stopped.returncode, 0)
        self.assertEqual(stopped.stdout, "M*W\n")


class _TTY(io.StringIO):
    def isatty(self):
        return True


def _run_main(argv, stdin=None):
    stdout = io.StringIO()
    stderr = io.StringIO()
    if stdin is None:
        stdin = io.StringIO("")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    try:
        sys.stdout = stdout
        sys.stderr = stderr
        code = main(argv, stdin=stdin)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
    return code, stdout.getvalue(), stderr.getvalue()


def _run_script(argv, stdin_text=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
