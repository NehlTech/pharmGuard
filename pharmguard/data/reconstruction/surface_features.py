"""
Surface-feature counting and trimming for reconstructed payloads.

MPIB stores per-instance reconstruction targets in the field
``reconstruction_hook.features`` with four dimensions:

    lines        Number of newline-separated lines.
    words        Whitespace-tokenized word count.
    headers      Markdown-style header count (lines starting with '#').
    formatting   Count of formatting markers: '**', '*', '-', '|', '`'.

For each generated payload we count these on the produced text and
compare to the target. If we are far above the target on words or
lines, we trim. If we are far below, we mark the instance as
"undersize" but keep it (we would rather have undersized clinical
content than reject a generation that is otherwise sound).

We do NOT use generation-time conditioning to hit the target exactly.
The target is a soft constraint to keep our reconstructions in the
same surface-form regime as MPIB's originals; deviations are logged
and reported as a quality metric, not enforced as a hard requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Patterns used for counting formatting marks.
# We deliberately count marker *occurrences* rather than tokens so that
# bullet lists and bold spans both contribute proportionally.
_FORMATTING_PATTERN = re.compile(r"\*\*|\*|^\s*-\s|\||`", re.MULTILINE)


@dataclass(frozen=True)
class SurfaceFeatures:
    """Counts of structural/formatting elements in a payload string."""

    lines:      int
    words:      int
    headers:    int
    formatting: int

    def to_dict(self) -> dict:
        return {
            "lines":      self.lines,
            "words":      self.words,
            "headers":    self.headers,
            "formatting": self.formatting,
        }


def count_features(text: str) -> SurfaceFeatures:
    """Count the four MPIB surface features in ``text``."""
    if not text:
        return SurfaceFeatures(lines=0, words=0, headers=0, formatting=0)

    # Lines: split on newlines, drop trailing empty.
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    n_lines = max(1, len(lines))  # treat any non-empty text as ≥1 line

    # Words: simple whitespace tokenization.
    n_words = len(text.split())

    # Headers: lines starting with one or more '#' followed by space.
    n_headers = sum(
        1 for line in lines
        if re.match(r"^\s*#{1,6}\s", line)
    )

    # Formatting marks.
    n_formatting = len(_FORMATTING_PATTERN.findall(text))

    return SurfaceFeatures(
        lines=n_lines,
        words=n_words,
        headers=n_headers,
        formatting=n_formatting,
    )


def feature_deviation(
    actual: SurfaceFeatures,
    target: dict,
) -> dict:
    """
    Compute fractional deviation per feature.

    Returns a dict with a fractional value per feature. A value of
    0.0 means we hit the target exactly; 0.20 means 20% over or
    under; sign is +/- to indicate direction. ``inf`` is returned
    when the target is zero and the actual is nonzero (we cannot
    take a ratio).
    """
    out = {}
    actual_d = actual.to_dict()
    for key in ("lines", "words", "headers", "formatting"):
        a = actual_d[key]
        t = int(target.get(key, 0))
        if t == 0:
            out[key] = 0.0 if a == 0 else float("inf")
        else:
            out[key] = (a - t) / t
    return out


def is_within_tolerance(
    deviation: dict,
    tolerance: float = 0.50,
) -> bool:
    """
    True if every per-feature absolute deviation is within ``tolerance``.

    A 50% default is intentionally lenient — we want most generations
    to land within tolerance, while still flagging extreme misses.
    """
    for key, dev in deviation.items():
        if dev == float("inf"):
            return False
        if abs(dev) > tolerance:
            return False
    return True


def trim_to_word_target(
    text: str,
    target_words: int,
    overshoot_factor: float = 1.30,
) -> str:
    """
    If ``text`` is more than ``overshoot_factor`` × ``target_words``
    long, trim it back to ``target_words`` at the nearest sentence
    boundary.

    Returns the (possibly trimmed) text. If the text is shorter than
    or equal to the threshold, returns it unchanged.
    """
    actual = len(text.split())
    if actual <= int(target_words * overshoot_factor):
        return text

    # Trim by finding the sentence boundary nearest to target_words.
    # Sentence boundaries: '. ', '! ', '? ', and end-of-text.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    rebuilt: list[str] = []
    word_count = 0
    for s in sentences:
        s_words = len(s.split())
        if word_count + s_words > target_words and rebuilt:
            break
        rebuilt.append(s)
        word_count += s_words

    return " ".join(rebuilt).strip()
