from __future__ import annotations

import math
import re
from pathlib import Path

from skip import Schematic as SkipSchematic

from kicad_tool.models import Component, Group, Net, PinConnection, Schematic

_GROUP_LABEL_Y_TOLERANCE = 3.0


def parse_schematic(path: str | Path) -> Schematic:
    skip_sch = SkipSchematic(str(path))
    lib_unit_pins = _build_lib_unit_pins(skip_sch)
    components, positions = _extract_components(skip_sch, lib_unit_pins)
    pin_names = _build_pin_name_map(skip_sch, lib_unit_pins)
    nets = _extract_nets(skip_sch, pin_names, lib_unit_pins)
    groups = _extract_groups(skip_sch, positions)
    return Schematic(components=components, nets=nets, groups=groups)


def _get_lib_symbol(sch: SkipSchematic, lib_id: str):
    attr_name = re.sub(r"[^a-zA-Z0-9_]", "_", lib_id)
    for name in (attr_name, "n" + attr_name):
        try:
            return getattr(sch.lib_symbols, name)
        except AttributeError:
            continue
    return None


def _is_power_only_unit(
    lib_unit_pins: dict[tuple[str, int], dict[str, object]],
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


def _find_multi_unit_refs(sch: SkipSchematic) -> set[str]:
    units_per_ref: dict[str, set[int]] = {}
    for sym in sch.symbol:
        if sym.is_power:
            continue
        ref = sym.property.Reference.value
        units_per_ref.setdefault(ref, set()).add(sym.unit.value)
    return {ref for ref, units in units_per_ref.items() if len(units) > 1}


def _resolve_comp_ref(
    base_ref: str,
    unit_num: int,
    lib_id: str,
    multi_unit_refs: set[str],
    lib_unit_pins: dict[tuple[str, int], dict[str, object]],
) -> str:
    if base_ref in multi_unit_refs:
        if _is_power_only_unit(lib_unit_pins, lib_id, unit_num):
            return base_ref
        return f"{base_ref}{chr(ord('A') + unit_num - 1)}"
    return base_ref


def _extract_components(
    sch: SkipSchematic,
    lib_unit_pins: dict[tuple[str, int], dict[str, object]],
) -> tuple[list[Component], dict[str, tuple[float, float]]]:
    multi_unit_refs = _find_multi_unit_refs(sch)

    seen: set[str] = set()
    components = []
    positions: dict[str, tuple[float, float]] = {}
    for sym in sch.symbol:
        if sym.is_power:
            continue
        base_ref = sym.property.Reference.value
        unit_num = sym.unit.value
        lib_id = sym.lib_id.value

        reference = _resolve_comp_ref(base_ref, unit_num, lib_id, multi_unit_refs, lib_unit_pins)
        if reference == base_ref and base_ref in multi_unit_refs:
            continue

        if reference in seen:
            continue
        seen.add(reference)

        value = sym.property.Value.value
        try:
            footprint = sym.property.Footprint.value
        except (AttributeError, KeyError):
            footprint = ""
        props = {}
        for prop in sym.property:
            if prop.name not in ("Reference", "Value", "Footprint", "Datasheet"):
                props[prop.name] = prop.value
        components.append(Component(
            reference=reference,
            value=value,
            footprint=footprint,
            base_ref=base_ref,
            properties=props,
        ))
        positions[reference] = (sym.at.value[0], sym.at.value[1])
    return components, positions


def _parse_lib_sub_unit(sub) -> int:
    raw_name = sub.raw[1]
    parts = raw_name.rsplit("_", 2)
    return int(parts[-2])


def _build_lib_unit_pins(sch: SkipSchematic) -> dict[tuple[str, int], dict[str, object]]:
    """Map (lib_id, unit_number) to {pin_number: lib_pin_object}.

    Unit 0 in the library means shared across all units.
    """
    seen_libs: set[str] = set()
    result: dict[tuple[str, int], dict[str, object]] = {}

    for sym in sch.symbol:
        if sym.is_power:
            continue
        lib_id = sym.lib_id.value
        if lib_id in seen_libs:
            continue
        seen_libs.add(lib_id)
        lib_sym = _get_lib_symbol(sch, lib_id)
        if lib_sym is None:
            continue
        for sub in lib_sym.symbol:
            if not hasattr(sub, "pin") or sub.pin is None:
                continue
            sub_unit = _parse_lib_sub_unit(sub)
            key = (lib_id, sub_unit)
            if key in result:
                continue
            pin_map: dict[str, object] = {}
            for pin in sub.pin:
                pin_map[str(pin.number.value)] = pin
            result[key] = pin_map

    return result


def _get_unit_pins(
    lib_unit_pins: dict[tuple[str, int], dict[str, object]],
    lib_id: str,
    unit_num: int,
) -> dict[str, object]:
    pins = dict(lib_unit_pins.get((lib_id, 0), {}))
    if unit_num != 0:
        pins.update(lib_unit_pins.get((lib_id, unit_num), {}))
    return pins


def _build_pin_name_map(
    sch: SkipSchematic,
    lib_unit_pins: dict[tuple[str, int], dict[str, object]],
) -> dict[tuple[str, str], str]:
    lib_pin_names: dict[str, dict[str, str]] = {}
    for sym in sch.symbol:
        if sym.is_power:
            continue
        lib_id = sym.lib_id.value
        if lib_id in lib_pin_names:
            continue
        lib_sym = _get_lib_symbol(sch, lib_id)
        if lib_sym is None:
            continue
        pin_map: dict[str, str] = {}
        for sub in lib_sym.symbol:
            if not hasattr(sub, "pin") or sub.pin is None:
                continue
            for pin in sub.pin:
                number = str(pin.number.value)
                name = str(pin.name.value)
                if name and name != "~":
                    pin_map[number] = name
        lib_pin_names[lib_id] = pin_map

    multi_unit_refs = _find_multi_unit_refs(sch)

    result: dict[tuple[str, str], str] = {}
    for sym in sch.symbol:
        if sym.is_power:
            continue
        base_ref = sym.property.Reference.value
        lib_id = sym.lib_id.value
        unit_num = sym.unit.value
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


def _pin_location(sym, lib_pin) -> tuple[float, float]:
    sx, sy = sym.at.value[0], sym.at.value[1]
    sym_rot = sym.at.value[2] if len(sym.at.value) > 2 else 0

    px, py = lib_pin.at.value[0], lib_pin.at.value[1]

    theta = math.radians(sym_rot)
    rx = px * math.cos(theta) - py * math.sin(theta)
    ry = px * math.sin(theta) + py * math.cos(theta)

    if hasattr(sym, "mirror") and sym.mirror is not None:
        try:
            mval = sym.mirror.value
            if hasattr(mval, "value"):
                mval = mval.value()
            if mval == "x":
                ry = -ry
            elif mval == "y":
                rx = -rx
        except (AttributeError, TypeError):
            pass

    return _coord_key(sx + rx, sy - ry)


def _extract_groups(
    sch: SkipSchematic,
    positions: dict[str, tuple[float, float]],
) -> list[Group]:
    rects = []
    for r in sch.rectangle:
        x1, y1 = r.start.value[0], r.start.value[1]
        x2, y2 = r.end.value[0], r.end.value[1]
        rects.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    texts = []
    if hasattr(sch, "text") and sch.text is not None:
        for t in sch.text:
            texts.append((t.value, t.at.value[0], t.at.value[1]))

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
    sch: SkipSchematic,
    pin_names: dict[tuple[str, str], str],
    lib_unit_pins: dict[tuple[str, int], dict[str, object]],
) -> list[Net]:
    uf = _UnionFind()

    pin_at_coord: dict[tuple[float, float], list[tuple[str, str]]] = {}
    label_at_coord: dict[tuple[float, float], str] = {}
    power_net_names: set[str] = set()

    multi_unit_refs = _find_multi_unit_refs(sch)

    for sym in sch.symbol:
        if sym.is_power:
            value = sym.property.Value.value
            if value == "PWR_FLAG":
                continue
            at = sym.at.value
            coord = _coord_key(at[0], at[1])
            uf.find(coord)
            power_net_names.add(value)
            label_at_coord[coord] = value
            continue
        base_ref = sym.property.Reference.value
        lib_id = sym.lib_id.value
        unit_num = sym.unit.value
        unit_pins = _get_unit_pins(lib_unit_pins, lib_id, unit_num)
        comp_ref = _resolve_comp_ref(base_ref, unit_num, lib_id, multi_unit_refs, lib_unit_pins)

        for pin_number, lib_pin in unit_pins.items():
            coord = _pin_location(sym, lib_pin)
            uf.find(coord)
            resolved = pin_names.get((comp_ref, pin_number), pin_number)
            pin_at_coord.setdefault(coord, []).append((comp_ref, resolved))

    for wire in sch.wire:
        start = _coord_key(wire.start.value[0], wire.start.value[1])
        end = _coord_key(wire.end.value[0], wire.end.value[1])
        uf.union(start, end)

    for junc in sch.junction:
        coord = _coord_key(junc.at.value[0], junc.at.value[1])
        uf.find(coord)

    for label in sch.label:
        coord = _coord_key(label.at.value[0], label.at.value[1])
        uf.find(coord)
        label_at_coord[coord] = label.value

    for glabel in sch.global_label:
        coord = _coord_key(glabel.at.value[0], glabel.at.value[1])
        uf.find(coord)
        label_at_coord[coord] = glabel.value

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
