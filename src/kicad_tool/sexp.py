from __future__ import annotations


def parse_sexp(text: str) -> list:
    tokens = _tokenize(text)
    result, _ = _parse_tokens(tokens, 0)
    return result


def _tokenize(text: str) -> list[str]:
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\n\r":
            i += 1
        elif c == "(":
            tokens.append("(")
            i += 1
        elif c == ")":
            tokens.append(")")
            i += 1
        elif c == '"':
            j = i + 1
            parts = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    parts.append(text[j + 1])
                    j += 2
                else:
                    parts.append(text[j])
                    j += 1
            tokens.append('"' + "".join(parts) + '"')
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\n\r()\"":
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _parse_tokens(tokens: list[str], pos: int) -> tuple[list, int]:
    pos += 1  # skip opening paren
    items: list = []
    while pos < len(tokens) and tokens[pos] != ")":
        if tokens[pos] == "(":
            child, pos = _parse_tokens(tokens, pos)
            items.append(child)
        else:
            items.append(_atom(tokens[pos]))
            pos += 1
    return items, pos + 1  # skip closing paren


def _atom(token: str):
    if token.startswith('"'):
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


class SexpNode:
    __slots__ = ("_data",)

    def __init__(self, data: list):
        self._data = data

    @property
    def tag(self) -> str:
        return str(self._data[0])

    @property
    def value(self):
        return self._data[1] if len(self._data) > 1 else None

    @property
    def values(self) -> list:
        return [x for x in self._data[1:] if not isinstance(x, list)]

    @property
    def raw(self) -> list:
        return self._data

    def child(self, tag: str) -> SexpNode | None:
        for item in self._data[1:]:
            if isinstance(item, list) and item and str(item[0]) == tag:
                return SexpNode(item)
        return None

    def children(self, tag: str):
        for item in self._data[1:]:
            if isinstance(item, list) and item and str(item[0]) == tag:
                yield SexpNode(item)

    def has(self, tag: str) -> bool:
        return self.child(tag) is not None
