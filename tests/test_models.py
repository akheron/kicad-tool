from kicad_tool.models import Component, Group, PinConnection, Net, Schematic


def test_component_creation():
    comp = Component(
        reference="R1",
        value="10k",
        footprint="0402",
        base_ref="R1",
        properties={"MPN": "RC0402FR-0710KL"},
    )
    assert comp.reference == "R1"
    assert comp.value == "10k"
    assert comp.footprint == "0402"
    assert comp.base_ref == "R1"
    assert comp.properties == {"MPN": "RC0402FR-0710KL"}


def test_component_default_properties():
    comp = Component(reference="R1", value="10k", footprint="0402", base_ref="R1")
    assert comp.properties == {}


def test_pin_connection():
    conn = PinConnection(component_ref="U1", pin_name="PA0")
    assert conn.component_ref == "U1"
    assert conn.pin_name == "PA0"


def test_net_with_named_net():
    net = Net(
        name="I2C_SDA",
        connections=[
            PinConnection("U1", "PB7"),
            PinConnection("R1", "1"),
        ],
        is_power=False,
    )
    assert net.name == "I2C_SDA"
    assert len(net.connections) == 2
    assert not net.is_power


def test_net_power():
    net = Net(
        name="VCC",
        connections=[PinConnection("U1", "VDD"), PinConnection("R1", "1")],
        is_power=True,
    )
    assert net.is_power


def test_group_dataclass():
    """Group holds a name and sorted list of component references."""
    group = Group(name="Power", references=["C1", "D1", "D2"])
    assert group.name == "Power"
    assert group.references == ["C1", "D1", "D2"]


def test_schematic_has_groups():
    """Schematic includes groups list, defaulting to empty."""
    sch = Schematic(components=[], nets=[])
    assert sch.groups == []
