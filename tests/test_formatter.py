from kicad_tool.models import Component, Group, PinConnection, Net, Schematic
from kicad_tool.formatter import format_netlist, format_summary, format_bom, format_groups


def _make_test_schematic():
    """Simple circuit: U1 -> R1 -> D1, with VCC and GND power nets."""
    components = [
        Component("U1", "STM32F103", "LQFP-48", "U1"),
        Component("R1", "220", "0402", "R1"),
        Component("D1", "RED", "LED_0805", "D1"),
    ]
    nets = [
        Net("VCC", [PinConnection("U1", "VDD")], is_power=True),
        Net("GND", [PinConnection("U1", "VSS"), PinConnection("D1", "K")], is_power=True),
        Net("LED_DRIVE", [PinConnection("U1", "PA0"), PinConnection("R1", "1")]),
        Net(None, [PinConnection("R1", "2"), PinConnection("D1", "A")]),
    ]
    return Schematic(components=components, nets=nets)


def test_format_full_output():
    sch = _make_test_schematic()
    output = format_netlist(sch)

    assert "U1  STM32F103  LQFP-48" in output
    assert "R1  220  0402" in output
    assert "D1  RED  LED_0805" in output

    # Power connections use <-
    assert "VDD  <- VCC" in output
    assert "VSS  <- GND" in output
    assert "K  <- GND" in output

    # Signal connections use -- with net name
    assert "PA0  -- R1:1  (LED_DRIVE)" in output

    # Unnamed net has no parenthetical
    lines = output.splitlines()
    r1_pin2_line = [l for l in lines if "2  -- D1:A" in l]
    assert len(r1_pin2_line) == 1
    assert "(" not in r1_pin2_line[0]


def test_format_custom_properties():
    components = [
        Component("R1", "10k", "0402", "R1", {"MPN": "RC0402FR-0710KL"}),
    ]
    nets = []
    sch = Schematic(components=components, nets=nets)
    output = format_netlist(sch)
    assert 'R1  10k  0402  {MPN: RC0402FR-0710KL}' in output


def test_format_summary():
    sch = _make_test_schematic()
    output = format_summary(sch)
    assert "Components: 3" in output
    assert "Nets: 4" in output
    assert "U1" in output
    assert "R1" in output
    assert "LED_DRIVE" in output


def test_format_filtered_by_component():
    sch = _make_test_schematic()
    output = format_netlist(sch, components_filter={"R1"})
    assert "R1  220  0402" in output
    assert "U1  STM32F103" not in output
    assert "D1  RED" not in output


def test_format_netlist_shows_group():
    components = [
        Component("U1", "STM32F103", "LQFP-48", "U1"),
        Component("R1", "220", "0402", "R1"),
    ]
    nets = [
        Net("SIG", [PinConnection("U1", "PA0"), PinConnection("R1", "1")]),
    ]
    groups = [Group(name="Power", references=["R1"])]
    sch = Schematic(components=components, nets=nets, groups=groups)
    output = format_netlist(sch)
    assert "R1  220  0402  [Power]" in output
    # U1 is not in any group, no bracket
    assert "U1  STM32F103  LQFP-48" in output
    assert "[" not in output.splitlines()[0]  # U1 line has no group


def test_format_bom():
    sch = _make_test_schematic()
    output = format_bom(sch)
    lines = output.strip().splitlines()

    # Header row has Ref, Value, Footprint but no Pins
    assert "Ref" in lines[0]
    assert "Value" in lines[0]
    assert "Footprint" in lines[0]
    assert "Pins" not in lines[0]

    # Components sorted alphabetically
    data_lines = [l for l in lines[1:] if l.strip()]
    refs = [l.split()[0] for l in data_lines]
    assert refs == sorted(refs)

    assert any("D1" in l and "RED" in l and "LED_0805" in l for l in data_lines)
    assert any("R1" in l and "220" in l and "0402" in l for l in data_lines)
    assert any("U1" in l and "STM32F103" in l and "LQFP-48" in l for l in data_lines)


def test_format_bom_refs_filter():
    sch = _make_test_schematic()
    output = format_bom(sch, refs_filter={"R1", "D1"})
    lines = output.strip().splitlines()

    # Header is present
    assert "Ref" in lines[0]

    # Only R1 and D1, not U1
    data_lines = [l for l in lines[1:] if l.strip()]
    refs = [l.split()[0] for l in data_lines]
    assert "R1" in refs
    assert "D1" in refs
    assert "U1" not in refs


def test_format_bom_with_fields():
    """Custom fields appear as extra columns."""
    components = [
        Component("C1", "12pF", "C_0402", "C1", {"LCSC": "C76948", "MF": "muRata", "MP": "GRM1555"}),
        Component("U2", "CC1101", "RGP20", "U2", {"LCSC": "C2654650", "MF": "Texas Instruments"}),
    ]
    sch = Schematic(components=components, nets=[])
    output = format_bom(sch, fields=["LCSC", "MF", "MP"])
    lines = output.strip().splitlines()

    # Header has the extra field columns
    assert "LCSC" in lines[0]
    assert "MF" in lines[0]
    assert "MP" in lines[0]

    # C1 has all three fields
    c1_line = next(l for l in lines[1:] if l.startswith("C1"))
    assert "C76948" in c1_line
    assert "muRata" in c1_line
    assert "GRM1555" in c1_line

    # U2 has LCSC and MF but not MP — MP column should be empty
    u2_line = next(l for l in lines[1:] if l.startswith("U2"))
    assert "C2654650" in u2_line
    assert "Texas Instruments" in u2_line


def test_format_bom_fields_all():
    """--fields-all collects all custom property keys across all components."""
    components = [
        Component("C1", "12pF", "C_0402", "C1", {"LCSC": "C76948", "MF": "muRata"}),
        Component("R1", "10k", "R_0402", "R1", {"LCSC": "C123", "MP": "RC0402"}),
    ]
    sch = Schematic(components=components, nets=[])
    output = format_bom(sch, fields_all=True)
    lines = output.strip().splitlines()

    # All three unique property keys should appear in the header
    assert "LCSC" in lines[0]
    assert "MF" in lines[0]
    assert "MP" in lines[0]

    # C1 has LCSC and MF but not MP
    c1_line = next(l for l in lines[1:] if l.startswith("C1"))
    assert "C76948" in c1_line
    assert "muRata" in c1_line

    # R1 has LCSC and MP but not MF
    r1_line = next(l for l in lines[1:] if l.startswith("R1"))
    assert "C123" in r1_line
    assert "RC0402" in r1_line



def test_format_groups():
    groups = [
        Group(name="Power", references=["C1", "D1", "D2"]),
        Group(name="Logic", references=["U1A", "U2A"]),
    ]
    output = format_groups(groups)
    assert "Power: C1, D1, D2" in output
    assert "Logic: U1A, U2A" in output


def test_format_groups_with_ungrouped():
    groups = [
        Group(name="Power", references=["C1"]),
        Group(name="Ungrouped", references=["J1", "R99"]),
    ]
    output = format_groups(groups)
    assert "Power: C1" in output
    assert "Ungrouped: J1, R99" in output
