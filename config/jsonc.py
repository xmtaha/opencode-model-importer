"""Lossless JSONC scanning.

The config file is edited by inserting text at known JSON positions, so every
comment, trailing comma and formatting choice in the original stays byte-for-byte
unchanged. Only parsing lives here; text insertion lives in opencode_config.
"""

import json
from dataclasses import dataclass, field

from utils.i18n import tr


@dataclass
class Member:
    key: str
    value_start: int
    value_end: int
    key_start: int = 0  # index of the key's opening quote


@dataclass
class ObjectNode:
    start: int  # index of '{'
    end: int  # index just past '}'
    members: list[Member] = field(default_factory=list)
    # Whitespace/comment run after the '}' closing a trailing comma, i.e. the text
    # between the last member's comma and the final '}'.
    trailing: tuple[int, int] | None = None

    def value(self, key: str) -> int | None:
        for member in self.members:
            if member.key == key:
                return member.value_start
        return None


def skip_ws(text: str, i: int, end: int) -> int:
    """Skip whitespace and // or /* */ comments."""
    while i < end:
        if text[i] in " \t\r\n":
            i += 1
        elif text.startswith("//", i):
            newline = text.find("\n", i)
            i = end if newline < 0 else newline + 1
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            if close < 0:
                raise ValueError(tr("kapatılmamış /* yorumu"))
            i = close + 2
        else:
            break
    return i


def strip_comments(text: str) -> str:
    """Replace comments with spaces (newlines kept) so the offsets stay valid."""
    out = list(text)
    i, end = 0, len(text)
    while i < end:
        if text[i] == '"':
            i = _scan_string(text, i, end)
            continue
        stop = skip_ws(text, i, end)
        for k in range(i, stop):
            if out[k] != "\n":
                out[k] = " "
        i = stop if stop > i else i + 1
    return "".join(out)


def strip_jsonc(text: str) -> str:
    """Blank out comments and trailing commas so json.loads can validate JSONC input."""
    cleaned = strip_comments(text)
    out = list(cleaned)
    i, end = 0, len(cleaned)
    while i < end:
        ch = cleaned[i]
        if ch == '"':
            i = _scan_string(cleaned, i, end)
            continue
        if ch == ",":
            nxt = i + 1
            while nxt < end and cleaned[nxt] in " \t\r\n":
                nxt += 1
            if nxt < end and cleaned[nxt] in "}]":
                out[i] = " "
        i += 1
    return "".join(out)


def _scan_string(text: str, i: int, end: int) -> int:
    """Return the index just past the closing quote of the string starting at i."""
    i += 1
    while i < end:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == '"':
            return i + 1
        elif ch == "\n":
            break
        else:
            i += 1
    raise ValueError(tr("kapatılmamış dize"))


def _scan_value(text: str, i: int, end: int) -> int:
    if text[i] not in "{[":
        return _scan_string(text, i, end) if text[i] == '"' else _scan_primitive(text, i, end)
    depth = 0
    while i < end:
        if text[i] == '"':
            i = _scan_string(text, i, end)
            continue
        if text.startswith("//", i) or text.startswith("/*", i):
            i = skip_ws(text, i, end)
            continue
        if text[i] in "{[":
            depth += 1
        elif text[i] in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(tr("kapatılmamış süslü/köşeli parantez"))


def _scan_primitive(text: str, i: int, end: int) -> int:
    while i < end and text[i] not in ",}] \t\r\n":
        i += 1
    return i


def parse_object(text: str, start: int, value_end: int) -> ObjectNode:
    """Scan the object literal starting at text[start] == '{'."""
    node = ObjectNode(start, -1)
    i = skip_ws(text, start + 1, value_end)
    while True:
        if i >= value_end:
            raise ValueError(tr("kapatılmamış nesne"))
        if text[i] == "}":
            node.end = i + 1
            return node
        if text[i] != '"':
            raise ValueError(tr("nesne anahtarı bekleniyordu ({pos})").format(pos=i))
        key_start = i
        key_end = _scan_string(text, i, value_end)
        key = json.loads(text[i:key_end])
        i = skip_ws(text, key_end, value_end)
        if i >= value_end or text[i] != ":":
            raise ValueError(tr("':' bekleniyordu ({pos})").format(pos=i))
        start_value = skip_ws(text, i + 1, value_end)
        if start_value >= value_end:
            raise ValueError(tr("kapatılmamış nesne"))
        stop = skip_ws(text, _scan_value(text, start_value, value_end), value_end)
        node.members.append(Member(key, start_value, stop, key_start))
        if stop < value_end and text[stop] == ",":
            after = skip_ws(text, stop + 1, value_end)
            if after < value_end and text[after] == "}":
                node.trailing = (stop + 1, after)
                node.end = after + 1
                return node
            i = after
        elif stop < value_end and text[stop] == "}":
            node.end = stop + 1
            return node
        else:
            raise ValueError(tr("',' veya '}}' bekleniyordu ({pos})").format(pos=stop))
