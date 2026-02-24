import os
import shutil
import tempfile

import pytest

from kicad_tool.sexp import SexpNode, parse_sexp

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
HIRVI = os.path.join(FIXTURES, "hirvi.kicad_sch")


def _make_temp_copy():
    """Copy hirvi fixture to a temp file, return path."""
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    os.close(fd)
    shutil.copy2(HIRVI, path)
    return path


def _get_property(node, name):
    for prop in node.children("property"):
        if prop.value == name:
            return str(prop.raw[2]) if len(prop.raw) > 2 else ""
    return ""


def _find_symbols_by_ref(root, reference):
    """Find all symbol instances matching a base reference."""
    result = []
    for sym in root.children("symbol"):
        ref = _get_property(sym, "Reference")
        if ref == reference:
            result.append(sym)
    return result


def test_edit_existing_property():
    from kicad_tool.editor import set_properties

    path = _make_temp_copy()
    try:
        changes = set_properties(path, "C1", {"Value": "1000uF"})
        assert any("Value" in c for c in changes)

        with open(path) as f:
            data = parse_sexp(f.read())
        root = SexpNode(data)
        symbols = _find_symbols_by_ref(root, "C1")
        assert len(symbols) >= 1
        for sym in symbols:
            assert _get_property(sym, "Value") == "1000uF"
    finally:
        os.unlink(path)


def test_add_new_property():
    from kicad_tool.editor import set_properties

    path = _make_temp_copy()
    try:
        changes = set_properties(path, "C1", {"MPN": "ECA-1VHG471"})
        assert any("MPN" in c and "(new)" in c for c in changes)

        with open(path) as f:
            data = parse_sexp(f.read())
        root = SexpNode(data)
        symbols = _find_symbols_by_ref(root, "C1")
        for sym in symbols:
            assert _get_property(sym, "MPN") == "ECA-1VHG471"
            # Verify new property has effects with hide
            for prop in sym.children("property"):
                if prop.value == "MPN":
                    assert prop.child("effects") is not None
                    effects = prop.child("effects")
                    assert effects.child("font") is not None
                    assert effects.has("hide")
    finally:
        os.unlink(path)


def test_multi_unit_all_instances_updated():
    """U1 is a 40106 with 7 unit instances. Setting a property updates all."""
    from kicad_tool.editor import set_properties

    path = _make_temp_copy()
    try:
        changes = set_properties(path, "U1", {"Value": "40106B"})

        with open(path) as f:
            data = parse_sexp(f.read())
        root = SexpNode(data)
        symbols = _find_symbols_by_ref(root, "U1")
        assert len(symbols) >= 2  # Multi-unit: multiple instances
        for sym in symbols:
            assert _get_property(sym, "Value") == "40106B"
    finally:
        os.unlink(path)


def test_error_reference_not_found():
    from kicad_tool.editor import set_properties

    path = _make_temp_copy()
    try:
        with pytest.raises(ValueError, match="not found"):
            set_properties(path, "ZZZZ99", {"Value": "foo"})
    finally:
        os.unlink(path)


def test_error_cannot_edit_reference():
    from kicad_tool.editor import set_properties

    path = _make_temp_copy()
    try:
        with pytest.raises(ValueError, match="Reference"):
            set_properties(path, "C1", {"Reference": "C99"})
    finally:
        os.unlink(path)
