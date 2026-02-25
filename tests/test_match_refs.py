from kicad_tool.cli import match_refs


def test_match_refs_exact():
    assert match_refs(["R1", "R2", "C1"], "R1") == {"R1"}


def test_match_refs_glob():
    assert match_refs(["R1", "R2", "C1", "C2"], "R*") == {"R1", "R2"}


def test_match_refs_comma_separated():
    assert match_refs(["R1", "R2", "C1", "U1"], "R*,C1") == {"R1", "R2", "C1"}


def test_match_refs_no_match():
    assert match_refs(["R1", "R2"], "X*") == set()
