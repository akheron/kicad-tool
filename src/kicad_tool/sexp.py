from __future__ import annotations


class QuotedStr(str):
    """A string that was originally quoted in S-expression source."""
    pass


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
                    ch = text[j + 1]
                    if ch == "n":
                        parts.append("\n")
                    elif ch == "t":
                        parts.append("\t")
                    else:
                        parts.append(ch)
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
        return QuotedStr(token[1:-1])
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def serialize_sexp(data: list) -> str:
    return _serialize_node(data, 0) + "\n"


def _serialize_node(data: list, indent: int) -> str:
    has_child_lists = any(isinstance(item, list) for item in data[1:])

    if not has_child_lists:
        parts = [_format_atom(item) for item in data]
        return "\t" * indent + "(" + " ".join(parts) + ")"

    # Collect leading atoms (tag + args before first list child)
    leading = []
    list_children = []
    found_list = False
    for item in data:
        if isinstance(item, list):
            found_list = True
            list_children.append(item)
        elif not found_list:
            leading.append(_format_atom(item))

    prefix = "\t" * indent

    # KiCad packs sibling leaf-list children with the same tag on one line,
    # wrapping at ~120 chars (e.g. (pts (xy 1 2) (xy 3 4) (xy 5 6)))
    if len(list_children) > 1 and _all_same_tag_leaves(list_children):
        child_prefix = "\t" * (indent + 1)
        formatted = [
            "(" + " ".join(_format_atom(item) for item in child) + ")"
            for child in list_children
        ]
        # Pack children into lines, wrapping at ~120 chars
        packed_lines = []
        current = child_prefix
        for f in formatted:
            if current == child_prefix:
                current += f
            elif len(current) + 1 + len(f) <= 112:
                current += " " + f
            else:
                packed_lines.append(current)
                current = child_prefix + f
        packed_lines.append(current)
        lines = [prefix + "(" + " ".join(leading)]
        lines.extend(packed_lines)
        lines.append(prefix + ")")
        return "\n".join(lines)

    lines = [prefix + "(" + " ".join(leading)]
    for child in list_children:
        lines.append(_serialize_node(child, indent + 1))
    lines.append(prefix + ")")
    return "\n".join(lines)


def _all_same_tag_leaves(children: list[list]) -> bool:
    """Check if all child lists are leaf nodes (no nested lists) with the same tag."""
    tag = children[0][0]
    return all(
        child[0] == tag and not any(isinstance(item, list) for item in child[1:])
        for child in children
    )


def _format_atom(value) -> str:
    if isinstance(value, QuotedStr):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return f'"{escaped}"'
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


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
