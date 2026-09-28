#!/usr/bin/env python3
"""Translate a DNA or RNA sequence into amino acids.

Uses the standard genetic code and one-letter amino-acid symbols. DNA (T)
and RNA (U) codons are equivalent. Translation stops at the first in-frame
stop codon unless --through-stops is set.
"""

from __future__ import annotations

import argparse
import sys

# Standard genetic code in TCAG codon order (NCBI transl_table 1).
_AMINO_ACIDS = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
_BASES = "TCAG"


def _codon_table() -> dict[str, str]:
    table: dict[str, str] = {}
    index = 0
    for first in _BASES:
        for second in _BASES:
            for third in _BASES:
                table[first + second + third] = _AMINO_ACIDS[index]
                index += 1
    return table


CODON_TABLE = _codon_table()


class TranslationError(ValueError):
    """The nucleotide sequence or reading frame cannot be translated."""


def clean_sequence(sequence: str) -> str:
    """Return an uppercase DNA sequence, converting U to T.

    Spaces, tabs, and newlines are ignored. Any other character outside
    A, C, G, T, and U is rejected. A sequence that contains both T and U
    is rejected.
    """

    nucleotides: list[str] = []
    for char in sequence:
        if char in " \t\r\n":
            continue
        upper = char.upper()
        if upper not in "ACGTU":
            position = len(nucleotides) + 1
            raise TranslationError(f"invalid character {char!r} at position {position}")
        nucleotides.append(upper)
    cleaned = "".join(nucleotides)
    if "T" in cleaned and "U" in cleaned:
        raise TranslationError("sequence contains both T and U")
    return cleaned.replace("U", "T")


def leftover_note(count: int, frame: int) -> str:
    """Describe bases that did not form a complete codon."""

    if count == 1:
        return f"note: 1 leftover base in frame {frame} was not translated"
    return f"note: {count} leftover bases in frame {frame} were not translated"


def translate(sequence: str, frame: int = 1, through_stops: bool = False) -> tuple[str, int]:
    """Translate ``sequence`` and return ``(protein, leftover_base_count)``.

    ``frame`` is 1, 2, or 3. Stops end the protein unless ``through_stops``
    is true, in which case each stop is ``*``.
    """

    if frame not in (1, 2, 3):
        raise TranslationError("frame must be 1, 2, or 3")
    dna = clean_sequence(sequence)
    readable = dna[frame - 1 :]
    leftover = len(readable) % 3
    complete = readable[: len(readable) - leftover]
    amino_acids: list[str] = []
    for index in range(0, len(complete), 3):
        amino = CODON_TABLE[complete[index : index + 3]]
        if amino == "*" and not through_stops:
            break
        amino_acids.append(amino)
    return "".join(amino_acids), leftover


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Translate a DNA or RNA nucleotide sequence into an amino-acid "
            "sequence using the standard genetic code."
        )
    )
    parser.add_argument(
        "sequence",
        nargs="?",
        help="Nucleotide sequence. Read from stdin when omitted.",
    )
    parser.add_argument(
        "--frame",
        type=int,
        choices=(1, 2, 3),
        default=1,
        help="Reading frame: 1, 2, or 3 (default: 1).",
    )
    parser.add_argument(
        "--through-stops",
        action="store_true",
        help="Keep translating after stop codons and mark each stop as *.",
    )
    return parser


def main(argv: list[str] | None = None, stdin=None) -> int:
    """Run the translator. Return a process exit code."""

    args = build_parser().parse_args(argv)
    stream = sys.stdin if stdin is None else stdin
    try:
        if args.sequence is None:
            if stream.isatty():
                raise TranslationError("provide a nucleotide sequence as an argument or on stdin")
            raw = stream.read()
        else:
            raw = args.sequence
        protein, leftover = translate(raw, frame=args.frame, through_stops=args.through_stops)
    except TranslationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if leftover:
        print(leftover_note(leftover, args.frame), file=sys.stderr)
    print(protein)
    return 0


if __name__ == "__main__":
    sys.exit(main())
