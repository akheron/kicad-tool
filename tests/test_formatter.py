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


def test_format_bom():
    sch = _make_test_schematic()
    output = format_bom(sch)
    lines = output.strip().splitlines()

    # Header row
    assert "Ref" in lines[0]
    assert "Value" in lines[0]
    assert "Footprint" in lines[0]
    assert "Pins" in lines[0]

    # Components sorted alphabetically
    data_lines = [l for l in lines[1:] if l.strip()]
    refs = [l.split()[0] for l in data_lines]
    assert refs == sorted(refs)

    assert any("D1" in l and "RED" in l and "LED_0805" in l for l in data_lines)
    assert any("R1" in l and "220" in l and "0402" in l for l in data_lines)
    assert any("U1" in l and "STM32F103" in l and "LQFP-48" in l for l in data_lines)


def test_format_bom_pin_counts():
    """Pin count reflects number of net connections per component."""
    sch = _make_test_schematic()
    output = format_bom(sch)
    lines = output.strip().splitlines()[1:]

    # U1 has 3 connections: VDD (VCC), VSS (GND), PA0 (LED_DRIVE)
    u1_line = next(l for l in lines if l.startswith("U1"))
    assert u1_line.split()[-1] == "3"

    # R1 has 2 connections: pin 1 (LED_DRIVE), pin 2 (unnamed)
    r1_line = next(l for l in lines if l.startswith("R1"))
    assert r1_line.split()[-1] == "2"



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
