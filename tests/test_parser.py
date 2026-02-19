import os

import pytest

from kicad_tool.parser import parse_schematic

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
HIRVI = os.path.join(FIXTURES, "hirvi.kicad_sch")
JOLENE = os.path.join(FIXTURES, "jolene.kicad_sch")


@pytest.fixture
def hirvi_schematic():
    return parse_schematic(HIRVI)


def test_component_count():
    sch = parse_schematic(HIRVI)
    assert len(sch.components) == 58


def test_multi_unit_split():
    """Multi-unit ICs produce one component per functional unit."""
    sch = parse_schematic(HIRVI)
    refs = {c.reference for c in sch.components}
    for letter in "ABCDEF":
        assert f"U1{letter}" in refs
    for letter in "AB":
        assert f"U2{letter}" in refs
    for letter in "ABCD":
        assert f"U3{letter}" in refs
        assert f"U4{letter}" in refs


def test_multi_unit_base_ref():
    """Multi-unit components store the package reference in base_ref."""
    sch = parse_schematic(HIRVI)
    by_ref = {c.reference: c for c in sch.components}
    assert by_ref["U1A"].base_ref == "U1"
    assert by_ref["U2B"].base_ref == "U2"
    assert by_ref["R1"].base_ref == "R1"


def test_component_values():
    sch = parse_schematic(HIRVI)
    by_ref = {c.reference: c for c in sch.components}
    assert by_ref["U1A"].value == "40106"
    assert by_ref["R1"].value == "2.2K"
    assert by_ref["C1"].value == "470uF"
    assert by_ref["M1"].value == "Motor_DC"


def test_component_footprints():
    sch = parse_schematic(HIRVI)
    by_ref = {c.reference: c for c in sch.components}
    assert by_ref["U1A"].footprint == "Package_DIP:DIP-14_W7.62mm"
    assert by_ref["R1"].footprint == "Resistor_SMD:R_0805_2012Metric"


def test_power_nets():
    sch = parse_schematic(HIRVI)
    power = {n.name: n for n in sch.nets if n.is_power}
    assert "GND" in power
    assert "VCC" in power
    assert "+12V" in power


def test_gnd_net():
    """GND net should include IC power pins (base ref), bypass caps, and MOSFET sources."""
    sch = parse_schematic(HIRVI)
    gnd = next(n for n in sch.nets if n.name == "GND")
    conn_keys = {(c.component_ref, c.pin_name) for c in gnd.connections}
    assert ("U1", "VSS") in conn_keys
    assert ("U2", "VSS") in conn_keys
    assert ("Q4", "S") in conn_keys
    assert ("Q2", "S") in conn_keys


def test_vcc_net():
    sch = parse_schematic(HIRVI)
    vcc = next(n for n in sch.nets if n.name == "VCC")
    conn_keys = {(c.component_ref, c.pin_name) for c in vcc.connections}
    assert ("U1", "VDD") in conn_keys
    assert ("U2", "VDD") in conn_keys
    assert ("Q1", "S") in conn_keys
    assert ("Q3", "S") in conn_keys


def test_motor_nets():
    """Motor connects to H-bridge outputs and connector."""
    sch = parse_schematic(HIRVI)
    m_plus = next(n for n in sch.nets if n.name == "M+")
    m_minus = next(n for n in sch.nets if n.name == "M-")
    plus_refs = {c.component_ref for c in m_plus.connections}
    minus_refs = {c.component_ref for c in m_minus.connections}
    assert plus_refs == {"M1", "Q1", "Q2", "J1"}
    assert minus_refs == {"M1", "Q3", "Q4", "J1"}


def test_switch_nets():
    sch = parse_schematic(HIRVI)
    nets_by_name = {n.name: n for n in sch.nets if n.name}
    sw_on = nets_by_name["SW_ON{slash}OFF"]
    assert {c.component_ref for c in sw_on.connections} == {"SW1", "R9", "R11", "J1"}


def test_global_label_unification():
    """Global labels with the same name at different locations form one net."""
    sch = parse_schematic(HIRVI)
    m_plus_nets = [n for n in sch.nets if n.name == "M+"]
    assert len(m_plus_nets) == 1


def test_mosfet_pin_names():
    """MOSFET pins should use G/D/S names from library."""
    sch = parse_schematic(HIRVI)
    q1_pins = set()
    for net in sch.nets:
        for conn in net.connections:
            if conn.component_ref == "Q1":
                q1_pins.add(conn.pin_name)
    assert "G" in q1_pins
    assert "D" in q1_pins
    assert "S" in q1_pins


def test_resistor_pins_use_numbers():
    """Resistor pins named '~' in library should fall back to pin numbers."""
    sch = parse_schematic(HIRVI)
    r1_pins = set()
    for net in sch.nets:
        for conn in net.connections:
            if conn.component_ref == "R1":
                r1_pins.add(conn.pin_name)
    assert r1_pins == {"1", "2"}


def test_oscillator_connectivity():
    """U1E inverter (pin 11) connects to R13:2 and C5:2 (RC oscillator feedback)."""
    sch = parse_schematic(HIRVI)
    for net in sch.nets:
        conn_keys = {(c.component_ref, c.pin_name) for c in net.connections}
        if ("U1E", "11") in conn_keys:
            assert ("R13", "2") in conn_keys
            assert ("C5", "2") in conn_keys
            return
    raise AssertionError("No net found for U1E pin 11")


def test_gate_drive_connectivity():
    """R1 pin 1 connects to Q1 gate (MOSFET gate drive)."""
    sch = parse_schematic(HIRVI)
    for net in sch.nets:
        conn_keys = {(c.component_ref, c.pin_name) for c in net.connections}
        if ("R1", "1") in conn_keys:
            assert ("Q1", "G") in conn_keys
            return
    raise AssertionError("No net found connecting R1:1 to Q1:G")


def _nets_by_name(sch):
    return {n.name: n for n in sch.nets if n.name}


def _conn_keys(net):
    return {(c.component_ref, c.pin_name) for c in net.connections}


def test_multi_unit_pin_names():
    """U2 (4013) units have bare pin names without unit prefix."""
    sch = parse_schematic(HIRVI)
    u2a_pins = set()
    u2b_pins = set()
    for net in sch.nets:
        for conn in net.connections:
            if conn.component_ref == "U2A":
                u2a_pins.add(conn.pin_name)
            elif conn.component_ref == "U2B":
                u2b_pins.add(conn.pin_name)
    assert "R" in u2a_pins
    assert "Q" in u2a_pins
    assert "R" in u2b_pins
    assert "Q" in u2b_pins


def test_multi_unit_numbered_pins():
    """U3/U4 (4071/4081) use number pins without unit prefix."""
    sch = parse_schematic(HIRVI)
    u3a_pins = set()
    for net in sch.nets:
        for conn in net.connections:
            if conn.component_ref == "U3A":
                u3a_pins.add(conn.pin_name)
    assert "1" in u3a_pins
    assert "2" in u3a_pins


def test_u2_flipflop_a():
    """U2A: Q outputs ON, D/~{Q} on ~{ON}."""
    sch = parse_schematic(HIRVI)
    nets = _nets_by_name(sch)

    on = _conn_keys(nets["ON"])
    assert ("U2A", "Q") in on
    assert ("U4B", "5") in on
    assert ("U4C", "8") in on

    on_inv = _conn_keys(nets["~{ON}"])
    assert ("U2A", "D") in on_inv
    assert ("U2A", "~{Q}") in on_inv
    assert ("U3B", "5") in on_inv
    assert ("U3C", "9") in on_inv


def test_u2_flipflop_b():
    """U2B: R on RAJA1, S on RAJA2, Q outputs DIR, ~{Q} outputs ~{DIR}."""
    sch = parse_schematic(HIRVI)
    nets = _nets_by_name(sch)

    assert ("U2B", "R") in _conn_keys(nets["RAJA1"])
    assert ("U2B", "S") in _conn_keys(nets["RAJA2"])
    assert ("U2B", "Q") in _conn_keys(nets["DIR"])
    assert ("U2B", "~{Q}") in _conn_keys(nets["~{DIR}"])


def test_u3_gate_c_connections():
    """U3C (pins 8,9,10) was previously missing due to kicad-skip bug."""
    sch = parse_schematic(HIRVI)
    nets = _nets_by_name(sch)

    assert ("U3C", "8") in _conn_keys(nets["~{DIR}"])
    assert ("U3C", "9") in _conn_keys(nets["~{ON}"])

    for net in sch.nets:
        keys = _conn_keys(net)
        if ("U3C", "10") in keys:
            assert ("R5", "1") in keys
            assert ("R6", "2") in keys
            break
    else:
        raise AssertionError("No net found for U3C:10")


def test_u4_gate_c_connections():
    """U4C (pins 8,9,10) was previously missing due to kicad-skip bug."""
    sch = parse_schematic(HIRVI)
    nets = _nets_by_name(sch)

    assert ("U4C", "8") in _conn_keys(nets["ON"])
    assert ("U4C", "9") in _conn_keys(nets["DIR"])

    for net in sch.nets:
        keys = _conn_keys(net)
        if ("U4C", "10") in keys:
            assert ("R3", "1") in keys
            assert ("R4", "2") in keys
            break
    else:
        raise AssertionError("No net found for U4C:10")


def test_u3_internal_connection():
    """U3A output (pin 2) connects to U3D input (pin 11)."""
    sch = parse_schematic(HIRVI)
    for net in sch.nets:
        keys = _conn_keys(net)
        if ("U3A", "2") in keys:
            assert ("U3D", "11") in keys
            return
    raise AssertionError("No net found for U3A:2 -- U3D:11")


def test_unused_gate_pins():
    """Unused gates have floating pins: U1B/U1C outputs, U4A/U4D outputs."""
    sch = parse_schematic(HIRVI)
    all_pins: dict[tuple[str, str], str | None] = {}
    for net in sch.nets:
        for conn in net.connections:
            key = (conn.component_ref, conn.pin_name)
            all_pins[key] = net.name

    assert ("U1B", "4") not in all_pins or all_pins[("U1B", "4")] is None
    assert ("U1C", "6") not in all_pins or all_pins[("U1C", "6")] is None
    assert ("U4A", "3") not in all_pins or all_pins[("U4A", "3")] is None
    assert ("U4D", "11") not in all_pins or all_pins[("U4D", "11")] is None


def test_u1_inverter_assignments():
    """40106 hex inverter: 6 inverters U1A-U1F, each with 2 pins."""
    sch = parse_schematic(HIRVI)
    for letter in "ABCDEF":
        ref = f"U1{letter}"
        unit_pins = set()
        for net in sch.nets:
            for conn in net.connections:
                if conn.component_ref == ref:
                    unit_pins.add(conn.pin_name)
        assert len(unit_pins) == 2, f"{ref} should have 2 pins, got {unit_pins}"


def test_lib_id_with_special_characters():
    """Lib IDs with hyphens/dots (e.g. MIC5504-3.3YM5) resolve correctly."""
    sch = parse_schematic(JOLENE)
    u4_pins: dict[str, str | None] = {}
    for net in sch.nets:
        for conn in net.connections:
            if conn.component_ref == "U4":
                u4_pins[conn.pin_name] = net.name
    assert "VIN" in u4_pins
    assert "VOUT" in u4_pins
    assert "EN" in u4_pins
    assert "GND" in u4_pins


def test_jolene_i2c_bus():
    """SDA/SCL labels unify MCU, sensor, and pull-up resistors into shared nets."""
    sch = parse_schematic(JOLENE)
    nets = _nets_by_name(sch)

    sda = _conn_keys(nets["SDA"])
    assert ("U1", "PB11") in sda
    assert ("U3", "SDA") in sda
    assert ("R2", "2") in sda

    scl = _conn_keys(nets["SCL"])
    assert ("U1", "PB10") in scl
    assert ("U3", "SCL") in scl
    assert ("R3", "2") in scl


def test_jolene_spi_bus():
    """CS/SCK/MISO/MOSI labels unify MCU and radio into shared nets."""
    sch = parse_schematic(JOLENE)
    nets = _nets_by_name(sch)

    assert ("U1", "PB12") in _conn_keys(nets["CS"])
    assert ("U5", "CSN") in _conn_keys(nets["CS"])

    assert ("U1", "PB13") in _conn_keys(nets["SCK"])
    assert ("U5", "SCLK") in _conn_keys(nets["SCK"])

    assert ("U1", "PB14") in _conn_keys(nets["MISO"])
    assert ("U5", "SO/GDO1") in _conn_keys(nets["MISO"])

    assert ("U1", "PB15") in _conn_keys(nets["MOSI"])
    assert ("U5", "SI") in _conn_keys(nets["MOSI"])


def test_jolene_power_domains():
    """Multiple distinct power rails are extracted as separate power nets."""
    sch = parse_schematic(JOLENE)
    power = {n.name for n in sch.nets if n.is_power}
    assert {"GND", "VDD", "+5V", "I2C_VDD", "IRD_VDD"} <= power


def test_jolene_crystal_circuit():
    """Crystal Y1 pins 2/4 go to GND, pins 1/3 connect to U5 and load caps."""
    sch = parse_schematic(JOLENE)
    y1_pins: dict[str, set[tuple[str, str]]] = {}
    for net in sch.nets:
        keys = _conn_keys(net)
        for ref, pin in keys:
            if ref == "Y1":
                y1_pins[pin] = keys

    assert y1_pins["1"] & {("U5", "XOSC_Q1"), ("C81", "2")}
    assert y1_pins["3"] & {("U5", "XOSC_Q2"), ("C101", "2")}


def test_jolene_mid_wire_label():
    """Labels placed in the middle of a wire (not at an endpoint) still connect."""
    sch = parse_schematic(JOLENE)
    nets = _nets_by_name(sch)
    reset = _conn_keys(nets["~{RESET}"])
    assert ("U1", "NRST") in reset
    assert ("C8", "1") in reset
    assert ("J3", "Pin_5") in reset


@pytest.fixture
def jolene_schematic():
    return parse_schematic(JOLENE)


def test_jolene_groups(jolene_schematic):
    """Jolene has 7 labeled/unlabeled rectangle groups plus ungrouped components."""
    groups = jolene_schematic.groups
    named = {g.name: g for g in groups if g.name}
    unlabeled = [g for g in groups if g.name is None]

    assert "Indicator LED" in named
    assert "IR demodulator" in named
    assert "IR transmitter" in named
    assert "Temperature + humidity sensor" in named
    assert "Antenna, PI matching, test point" in named
    assert "Alternative 1: LDO regulator" in named
    assert "Ungrouped" in named

    assert len(unlabeled) == 1
    assert "U5" in unlabeled[0].references
    assert "Y1" in unlabeled[0].references


def test_jolene_unlabeled_group_contents(jolene_schematic):
    """Unlabeled RF transceiver rectangle captures the radio and matching network."""
    unlabeled = [g for g in jolene_schematic.groups if g.name is None]
    refs = set(unlabeled[0].references)
    assert "U5" in refs
    assert "Y1" in refs
    assert "L131" in refs
    assert "C51" in refs
    assert "FB165" in refs


def test_groups_from_hirvi(hirvi_schematic):
    """Parser extracts named groups from labeled rectangles in the schematic."""
    groups = hirvi_schematic.groups
    group_names = {g.name for g in groups}
    assert "Inputs & protection" in group_names
    assert "Buttons" in group_names
    assert "CD4xxx boilerplate" in group_names
    assert "Motor H-bridge" in group_names
    assert "Motor logic" in group_names


def test_group_component_assignment(hirvi_schematic):
    """Components are assigned to groups based on symbol position inside rectangles."""
    groups_by_name = {g.name: g for g in hirvi_schematic.groups}

    protection = groups_by_name["Inputs & protection"]
    assert "D1" in protection.references
    assert "D2" in protection.references
    assert "J1" in protection.references

    buttons = groups_by_name["Buttons"]
    assert "SW1" in buttons.references
    assert "U1F" in buttons.references

    hbridge = groups_by_name["Motor H-bridge"]
    assert "Q1" in hbridge.references
    assert "M1" in hbridge.references
    assert "U3B" in hbridge.references

    logic = groups_by_name["Motor logic"]
    assert "U1A" in logic.references
    assert "U2A" in logic.references

    boilerplate = groups_by_name["CD4xxx boilerplate"]
    assert "C8" in boilerplate.references
    assert "U4A" in boilerplate.references


def test_groups_references_sorted(hirvi_schematic):
    """References within each group are sorted."""
    for group in hirvi_schematic.groups:
        assert group.references == sorted(group.references)
