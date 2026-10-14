"""Editable common text with lossless, per-record mixed-section markers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import Match, SequenceMatcher


def _matching_blocks(first, other):
    """Use exact character matching for short text and bounded line matching for long text."""
    if first == other:
        return [Match(0, 0, len(first)), Match(len(first), len(other), 0)]
    if max(len(first), len(other)) <= 2048:
        return SequenceMatcher(None, first, other, autojunk=False).get_matching_blocks()

    prefix = 0
    while prefix < min(len(first), len(other)) and first[prefix] == other[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(first), len(other)) - prefix
        and first[len(first) - suffix - 1] == other[len(other) - suffix - 1]
    ):
        suffix += 1
    end_a, end_b = len(first) - suffix, len(other) - suffix
    left = first[prefix:end_a].splitlines(keepends=True)
    right = other[prefix:end_b].splitlines(keepends=True)
    offsets_a, offsets_b = [prefix], [prefix]
    for line in left:
        offsets_a.append(offsets_a[-1] + len(line))
    for line in right:
        offsets_b.append(offsets_b[-1] + len(line))
    blocks = [Match(0, 0, prefix)] if prefix else []
    cursor_a = cursor_b = prefix

    def refine(a, b):
        gap_a, gap_b = first[cursor_a:a], other[cursor_b:b]
        if max(len(gap_a), len(gap_b)) <= 2048 and len(gap_a) * len(gap_b) <= 1_000_000:
            blocks.extend(
                Match(cursor_a + block.a, cursor_b + block.b, block.size)
                for block in SequenceMatcher(
                    None, gap_a, gap_b, autojunk=False
                ).get_matching_blocks()
                if block.size
            )

    for block in SequenceMatcher(None, left, right, autojunk=True).get_matching_blocks():
        if not block.size:
            continue
        a, b = offsets_a[block.a], offsets_b[block.b]
        refine(a, b)
        size = offsets_a[block.a + block.size] - a
        blocks.append(Match(a, b, size))
        cursor_a, cursor_b = a + size, b + size
    refine(end_a, end_b)
    if suffix:
        blocks.append(Match(end_a, end_b, suffix))
    blocks.append(Match(len(first), len(other), 0))
    return blocks


def _intersect(left, right):
    result = []
    a = b = 0
    while a < len(left) and b < len(right):
        start = max(left[a][0], right[b][0])
        end = min(left[a][1], right[b][1])
        if start < end:
            result.append((start, end))
        if left[a][1] <= right[b][1]:
            a += 1
        else:
            b += 1
    return result


@dataclass
class MixedText:
    template: str
    sections: dict[str, tuple[str, ...]]
    opener: str = "⟦"
    closer: str = "⟧"

    @classmethod
    def from_values(cls, values):
        values = tuple(values)
        if not values:
            raise ValueError("Select at least one record.")
        delimiters = (("⟦", "⟧"), ("⟪", "⟫"), ("⌜", "⌟"))
        opener, closer = next(
            (
                (a, b)
                for a, b in delimiters
                if all(a not in value and b not in value for value in values)
            ),
            ("[[mixed:", "]]"),
        )
        while any(opener in value or closer in value for value in values):
            opener += ":"
            closer = ":" + closer
        first = values[0]
        if all(value == first for value in values):
            return cls(first, {}, opener, closer)
        matches = [_matching_blocks(first, value) for value in values]
        common = [(0, len(first))] if first else []
        for blocks in matches[1:]:
            common = _intersect(
                common, [(block.a, block.a + block.size) for block in blocks if block.size]
            )
        cursors = [0] * len(values)
        pointers = [0] * len(values)
        parts, sections = [], {}

        def append_gap(ends):
            gaps = tuple(value[start:end] for value, start, end in zip(values, cursors, ends))
            if all(gap == gaps[0] for gap in gaps):
                parts.append(gaps[0])
            else:
                token = f"{opener}{len(sections) + 1}{closer}"
                sections[token] = gaps
                parts.append(token)

        for start, end in common:
            positions = []
            for number, blocks in enumerate(matches):
                while blocks[pointers[number]].a + blocks[pointers[number]].size <= start:
                    pointers[number] += 1
                block = blocks[pointers[number]]
                positions.append(block.b + start - block.a)
            append_gap(positions)
            parts.append(first[start:end])
            cursors = [position + end - start for position in positions]
        append_gap([len(value) for value in values])
        return cls("".join(parts), sections, opener, closer)

    @property
    def pattern(self):
        return re.compile(re.escape(self.opener) + r"\d+" + re.escape(self.closer))

    def expand(self, edited: str, record_index: int) -> str:
        if not self.sections:
            return edited

        def replace(match):
            token = match.group()
            if token not in self.sections:
                raise ValueError(f"Unknown mixed-text marker {token}.")
            return self.sections[token][record_index]

        # Validate the editable template before inserting any original text.
        remainder = self.pattern.sub("", edited)
        if self.opener in remainder or self.closer in remainder:
            raise ValueError("Keep mixed markers intact, or replace/remove each complete marker.")
        return self.pattern.sub(replace, edited)
