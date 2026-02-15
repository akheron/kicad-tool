from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PinConnection:
    component_ref: str
    pin_name: str


@dataclass
class Net:
    name: str | None
    connections: list[PinConnection]
    is_power: bool = False


@dataclass
class Component:
    reference: str
    value: str
    footprint: str
    base_ref: str
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class Group:
    name: str | None
    references: list[str]


@dataclass
class Schematic:
    components: list[Component]
    nets: list[Net]
    groups: list[Group] = field(default_factory=list)
