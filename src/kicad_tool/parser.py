from __future__ import annotations

import math
from pathlib import Path

from kicad_tool.models import Component, Group, Net, PinConnection, Schematic
from kicad_tool.sexp import SexpNode, parse_sexp

_GROUP_LABEL_Y_TOLERANCE = 3.0


def parse_schematic(path: str | Path) -> Schematic:
    text = Path(path).read_text()
    root = SexpNode(parse_sexp(text))
    lib_unit_pins = _build_lib_unit_pins(root)
    components, positions = _extract_components(root, lib_unit_pins)
    pin_names = _build_pin_name_map(root, lib_unit_pins)
    nets = _extract_nets(root, pin_names, lib_unit_pins)
    groups = _extract_groups(root, positions)
    return Schematic(components=components, nets=nets, groups=groups)


def _get_property(node: SexpNode, name: str) -> str:
    for prop in node.children("property"):
        if prop.value == name:
            return str(prop.raw[2]) if len(prop.raw) > 2 else ""
    return ""


def _get_lib_symbol(root: SexpNode, lib_id: str) -> SexpNode | None:
    lib_symbols = root.child("lib_symbols")
    if lib_symbols is None:
        return None
    for sym in lib_symbols.children("symbol"):
        if sym.value == lib_id:
            return sym
    return None


def _is_power(sym: SexpNode) -> bool:
    ref = _get_property(sym, "Reference")
    return ref.startswith("#")


def _is_power_only_unit(
    lib_unit_pins: dict[tuple[str, int], dict[str, SexpNode]],
    lib_id: str,
    unit_num: int,
) -> bool:
    unit_own_pins = lib_unit_pins.get((lib_id, unit_num), {})
    if not unit_own_pins:
        return True
    return all(
        str(pin.raw[1]) == "power_in"
        for pin in unit_own_pins.values()
    )


def _find_multi_unit_refs(root: SexpNode) -> set[str]:
    units_per_ref: dict[str, set[int]] = {}
    for sym in root.children("symbol"):
        if _is_power(sym):
            continue
        ref = _get_property(sym, "Reference")
        units_per_ref.setdefault(ref, set()).add(sym.child("unit").value)
    return {ref for ref, units in units_per_ref.items() if len(units) > 1}


def _resolve_comp_ref(
    base_ref: str,
    unit_num: int,
    lib_id: str,
    multi_unit_refs: set[str],
    lib_unit_pins: dict[tuple[str, int], dict[str, SexpNode]],
) -> str:
    if base_ref in multi_unit_refs:
        if _is_power_only_unit(lib_unit_pins, lib_id, unit_num):
            return base_ref
        return f"{base_ref}{chr(ord('A') + unit_num - 1)}"
    return base_ref


def _extract_components(
    root: SexpNode,
    lib_unit_pins: dict[tuple[str, int], dict[str, SexpNode]],
) -> tuple[list[Component], dict[str, tuple[float, float]]]:
    multi_unit_refs = _find_multi_unit_refs(root)

    seen: set[str] = set()
    components = []
    positions: dict[str, tuple[float, float]] = {}
    for sym in root.children("symbol"):
        if _is_power(sym):
            continue
        base_ref = _get_property(sym, "Reference")
        unit_num = sym.child("unit").value
        lib_id = sym.child("lib_id").value

        reference = _resolve_comp_ref(base_ref, unit_num, lib_id, multi_unit_refs, lib_unit_pins)
        if reference == base_ref and base_ref in multi_unit_refs:
            continue

        if reference in seen:
            continue
        seen.add(reference)

        value = _get_property(sym, "Value")
        footprint = _get_property(sym, "Footprint")
        props = {}
        for prop in sym.children("property"):
            name = prop.value
            if name not in ("Reference", "Value", "Footprint", "Datasheet"):
                props[name] = str(prop.raw[2]) if len(prop.raw) > 2 else ""
        at = sym.child("at").values
        components.append(Component(
            reference=reference,
            value=value,
            footprint=footprint,
            base_ref=base_ref,
            properties=props,
        ))
        positions[reference] = (at[0], at[1])
    return components, positions


def _parse_lib_sub_unit(sub: SexpNode) -> int:
    raw_name = sub.value
    parts = raw_name.rsplit("_", 2)
    return int(parts[-2])


def _build_lib_unit_pins(root: SexpNode) -> dict[tuple[str, int], dict[str, SexpNode]]:
    """Map (lib_id, unit_number) to {pin_number: lib_pin_node}."""
    seen_libs: set[str] = set()
    result: dict[tuple[str, int], dict[str, SexpNode]] = {}

    for sym in root.children("symbol"):
        if _is_power(sym):
            continue
        lib_id = sym.child("lib_id").value
        if lib_id in seen_libs:
            continue
        seen_libs.add(lib_id)
        lib_sym = _get_lib_symbol(root, lib_id)
        if lib_sym is None:
            continue
        for sub in lib_sym.children("symbol"):
            pins = list(sub.children("pin"))
            if not pins:
                continue
            sub_unit = _parse_lib_sub_unit(sub)
            key = (lib_id, sub_unit)
            if key in result:
                continue
            pin_map: dict[str, SexpNode] = {}
            for pin in pins:
                pin_map[str(pin.child("number").value)] = pin
            result[key] = pin_map

    return result


def _get_unit_pins(
    lib_unit_pins: dict[tuple[str, int], dict[str, SexpNode]],
    lib_id: str,
    unit_num: int,
) -> dict[str, SexpNode]:
    pins = dict(lib_unit_pins.get((lib_id, 0), {}))
    if unit_num != 0:
        pins.update(lib_unit_pins.get((lib_id, unit_num), {}))
    return pins


def _build_pin_name_map(
    root: SexpNode,
    lib_unit_pins: dict[tuple[str, int], dict[str, SexpNode]],
) -> dict[tuple[str, str], str]:
    lib_pin_names: dict[str, dict[str, str]] = {}
    for sym in root.children("symbol"):
        if _is_power(sym):
            continue
        lib_id = sym.child("lib_id").value
        if lib_id in lib_pin_names:
            continue
        lib_sym = _get_lib_symbol(root, lib_id)
        if lib_sym is None:
            continue
        pin_map: dict[str, str] = {}
        for sub in lib_sym.children("symbol"):
            for pin in sub.children("pin"):
                number = str(pin.child("number").value)
                name = str(pin.child("name").value)
                if name and name != "~":
                    pin_map[number] = name
        lib_pin_names[lib_id] = pin_map

    multi_unit_refs = _find_multi_unit_refs(root)

    result: dict[tuple[str, str], str] = {}
    for sym in root.children("symbol"):
        if _is_power(sym):
            continue
        base_ref = _get_property(sym, "Reference")
        lib_id = sym.child("lib_id").value
        unit_num = sym.child("unit").value
        pin_map = lib_pin_names.get(lib_id, {})
        unit_pins = _get_unit_pins(lib_unit_pins, lib_id, unit_num)
        comp_ref = _resolve_comp_ref(base_ref, unit_num, lib_id, multi_unit_refs, lib_unit_pins)

        for pin_number in unit_pins:
            resolved = pin_map.get(pin_number, pin_number)
            result[(comp_ref, pin_number)] = resolved

    return result


class _UnionFind:
    def __init__(self):
        self._parent: dict = {}

    def find(self, x):
        if x not in self._parent:
            self._parent[x] = x
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> dict:
        result: dict = {}
        for key in self._parent:
            root = self.find(key)
            result.setdefault(root, []).append(key)
        return result


def _coord_key(x: float, y: float) -> tuple[float, float]:
    return (round(x, 2), round(y, 2))


def _point_on_wire(
    point: tuple[float, float],
    wire_start: tuple[float, float],
    wire_end: tuple[float, float],
    tol: float = 0.05,
) -> bool:
    px, py = point
    sx, sy = wire_start
    ex, ey = wire_end
    if abs(sy - ey) < tol and abs(py - sy) < tol:
        if min(sx, ex) - tol < px < max(sx, ex) + tol:
            return True
    if abs(sx - ex) < tol and abs(px - sx) < tol:
        if min(sy, ey) - tol < py < max(sy, ey) + tol:
            return True
    return False


def _pin_location(sym: SexpNode, lib_pin: SexpNode) -> tuple[float, float]:
    sym_at = sym.child("at").values
    sx, sy = sym_at[0], sym_at[1]
    sym_rot = sym_at[2] if len(sym_at) > 2 else 0

    pin_at = lib_pin.child("at").values
    px, py = pin_at[0], pin_at[1]

    theta = math.radians(sym_rot)
    rx = px * math.cos(theta) - py * math.sin(theta)
    ry = px * math.sin(theta) + py * math.cos(theta)

    mirror = sym.child("mirror")
    if mirror is not None:
        mval = mirror.value
        if mval == "x":
            ry = -ry
        elif mval == "y":
            rx = -rx

    return _coord_key(sx + rx, sy - ry)


def _extract_groups(
    root: SexpNode,
    positions: dict[str, tuple[float, float]],
) -> list[Group]:
    rects = []
    for r in root.children("rectangle"):
        start = r.child("start").values
        end = r.child("end").values
        x1, y1 = start[0], start[1]
        x2, y2 = end[0], end[1]
        rects.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    texts = []
    for t in root.children("text"):
        at = t.child("at").values
        texts.append((t.value, at[0], at[1]))

    labeled: set[int] = set()
    rect_names: dict[int, str] = {}
    for i, (rx1, ry1, rx2, ry2) in enumerate(rects):
        for tval, tx, ty in texts:
            if rx1 <= tx <= rx2 and abs(ty - ry1) <= _GROUP_LABEL_Y_TOLERANCE:
                labeled.add(i)
                rect_names[i] = tval
                break

    groups = []
    grouped_refs: set[str] = set()
    for i, (rx1, ry1, rx2, ry2) in enumerate(rects):
        refs = []
        for ref, (px, py) in positions.items():
            if rx1 <= px <= rx2 and ry1 <= py <= ry2:
                refs.append(ref)
        if not refs:
            continue
        if i not in labeled:
            name = None
        else:
            name = rect_names[i]
        grouped_refs.update(refs)
        groups.append(Group(name=name, references=sorted(refs)))

    ungrouped = sorted(set(positions.keys()) - grouped_refs)
    if ungrouped:
        groups.append(Group(name="Ungrouped", references=ungrouped))

    return groups


def _extract_nets(
    root: SexpNode,
    pin_names: dict[tuple[str, str], str],
    lib_unit_pins: dict[tuple[str, int], dict[str, SexpNode]],
) -> list[Net]:
    uf = _UnionFind()

    pin_at_coord: dict[tuple[float, float], list[tuple[str, str]]] = {}
    label_at_coord: dict[tuple[float, float], str] = {}
    power_net_names: set[str] = set()

    multi_unit_refs = _find_multi_unit_refs(root)

    for sym in root.children("symbol"):
        if _is_power(sym):
            value = _get_property(sym, "Value")
            if value == "PWR_FLAG":
                continue
            at = sym.child("at").values
            coord = _coord_key(at[0], at[1])
            uf.find(coord)
            power_net_names.add(value)
            label_at_coord[coord] = value
            continue
        base_ref = _get_property(sym, "Reference")
        lib_id = sym.child("lib_id").value
        unit_num = sym.child("unit").value
        unit_pins = _get_unit_pins(lib_unit_pins, lib_id, unit_num)
        comp_ref = _resolve_comp_ref(base_ref, unit_num, lib_id, multi_unit_refs, lib_unit_pins)

        for pin_number, lib_pin in unit_pins.items():
            coord = _pin_location(sym, lib_pin)
            uf.find(coord)
            resolved = pin_names.get((comp_ref, pin_number), pin_number)
            pin_at_coord.setdefault(coord, []).append((comp_ref, resolved))

    wire_segments = []
    for wire in root.children("wire"):
        pts = list(wire.child("pts").children("xy"))
        start = _coord_key(pts[0].values[0], pts[0].values[1])
        end = _coord_key(pts[1].values[0], pts[1].values[1])
        uf.union(start, end)
        wire_segments.append((start, end))

    for junc in root.children("junction"):
        at = junc.child("at").values
        coord = _coord_key(at[0], at[1])
        uf.find(coord)

    for label in root.children("label"):
        at = label.child("at").values
        coord = _coord_key(at[0], at[1])
        uf.find(coord)
        label_at_coord[coord] = label.value

    for glabel in root.children("global_label"):
        at = glabel.child("at").values
        coord = _coord_key(at[0], at[1])
        uf.find(coord)
        label_at_coord[coord] = glabel.value

    for coord in label_at_coord:
        for ws, we in wire_segments:
            if _point_on_wire(coord, ws, we):
                uf.union(coord, ws)
                break

    name_to_coords: dict[str, list[tuple[float, float]]] = {}
    for coord, name in label_at_coord.items():
        name_to_coords.setdefault(name, []).append(coord)
    for coords in name_to_coords.values():
        for c in coords[1:]:
            uf.union(coords[0], c)

    groups = uf.groups()
    nets = []
    for _root, coords in groups.items():
        connections = []
        name = None
        is_power = False
        for coord in coords:
            if coord in pin_at_coord:
                for ref, pin_num in pin_at_coord[coord]:
                    connections.append(PinConnection(ref, pin_num))
            if coord in label_at_coord:
                lbl = label_at_coord[coord]
                if lbl in power_net_names:
                    is_power = True
                name = lbl

        if connections:
            nets.append(Net(name=name, connections=connections, is_power=is_power))

    return nets
