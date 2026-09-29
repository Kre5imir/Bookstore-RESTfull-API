# Nucleotide translator

Translate a DNA or RNA sequence into a protein using the standard genetic code (one-letter amino-acid codes). The translator is a single command-line script and uses only the Python standard library.

DNA (`T`) and RNA (`U`) are detected from the sequence and share the same codon table. A sequence that contains both `T` and `U` is rejected. Letters may be upper or lower case. Spaces, tabs, and newlines are ignored. Any other character is an error.

Translation uses reading frame 1 unless you choose another frame. It stops at the first in-frame stop codon. With `--through-stops`, translation continues and each stop is written as `*`. Only complete codons are translated. If bases remain after the last complete codon in the chosen frame, a short note goes to stderr and the protein from the complete codons is still printed on stdout.

## Usage

```bash
python3 nucleotide/translate.py ATGCCCAAATAG
# MPK

python3 nucleotide/translate.py --frame 2 AATGGC
# M
# note: 2 leftover bases in frame 2 were not translated

python3 nucleotide/translate.py --through-stops ATGTAATAG
# M**

printf 'AUGGCUUCAAAAUAG\n' | python3 nucleotide/translate.py
# MASK
```

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `sequence` | read stdin | Nucleotide sequence. Optional positional argument. |
| `--frame 1\|2\|3` | `1` | Reading frame. Frame 2 skips the first base; frame 3 skips the first two. |
| `--through-stops` | off | Keep going after stop codons and write them as `*`. Without this flag, translation stops at the first in-frame stop and the stop is omitted. |

Exit status is `0` after a translation, `1` when the sequence is invalid or missing, and `2` when the arguments themselves are invalid.

## Tests

```bash
python3 -m unittest nucleotide.test_translate
```
