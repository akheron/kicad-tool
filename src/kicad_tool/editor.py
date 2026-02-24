from __future__ import annotations

from pathlib import Path

from kicad_tool.sexp import QuotedStr, SexpNode, parse_sexp, serialize_sexp


def set_properties(
    file_path: str | Path,
    reference: str,
    properties: dict[str, str],
) -> list[str]:
    if "Reference" in properties:
        raise ValueError("Cannot edit the Reference property")

    path = Path(file_path)
    text = path.read_text()
    root_data = parse_sexp(text)
    root = SexpNode(root_data)

    matched = _find_symbols(root, reference)
    if not matched:
        raise ValueError(f"Reference '{reference}' not found")

    changes = []
    first = True
    for sym in matched:
        for key, value in properties.items():
            _set_or_add_property(sym, key, value, changes if first else None)
        first = False

    path.write_text(serialize_sexp(root_data))
    return changes


def _find_symbols(root: SexpNode, reference: str) -> list[SexpNode]:
    result = []
    for sym in root.children("symbol"):
        for prop in sym.children("property"):
            if prop.value == "Reference":
                ref_val = str(prop.raw[2]) if len(prop.raw) > 2 else ""
                if ref_val == reference:
                    result.append(sym)
                break
    return result


def _set_or_add_property(
    sym: SexpNode, key: str, value: str, changes: list[str] | None
) -> None:
    for prop in sym.children("property"):
        if prop.value == key:
            old_value = str(prop.raw[2]) if len(prop.raw) > 2 else ""
            prop.raw[2] = QuotedStr(value)
            if changes is not None:
                changes.append(f"{key}: {old_value} -> {value}")
            return

    # Property doesn't exist — insert after last existing property
    new_prop = [
        "property",
        QuotedStr(key),
        QuotedStr(value),
        ["at", 0, 0, 0],
        ["effects",
            ["font",
                ["size", 1.27, 1.27],
            ],
            ["hide", "yes"],
        ],
    ]
    insert_idx = _find_last_property_index(sym.raw)
    sym.raw.insert(insert_idx + 1, new_prop)
    if changes is not None:
        changes.append(f"{key}: (new) {value}")


def _find_last_property_index(raw: list) -> int:
    last = 0
    for i, item in enumerate(raw[1:], 1):
        if isinstance(item, list) and item and str(item[0]) == "property":
            last = i
    return last
