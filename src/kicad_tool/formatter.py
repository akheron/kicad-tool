from kicad_tool.models import Group, Schematic, Net, PinConnection


def format_netlist(schematic: Schematic, components_filter: set[str] | None = None) -> str:
    pin_to_nets = _build_pin_index(schematic.nets)
    ref_to_group = _build_ref_to_group(schematic.groups)

    lines = []
    for comp in schematic.components:
        if components_filter and comp.reference not in components_filter:
            continue
        lines.append(_format_component_header(comp, ref_to_group.get(comp.reference)))
        pins_on_nets = _get_component_pins(comp.reference, pin_to_nets)
        for pin_name, net, peers in pins_on_nets:
            lines.append(_format_pin_line(pin_name, net, peers, comp.reference))
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def format_summary(schematic: Schematic) -> str:
    refs = sorted(c.reference for c in schematic.components)
    net_names = sorted(n.name for n in schematic.nets if n.name)
    lines = [
        f"Components: {len(schematic.components)}",
        f"Nets: {len(schematic.nets)}",
        "",
        "References: " + ", ".join(refs),
        "",
        "Named nets: " + ", ".join(net_names) if net_names else "Named nets: (none)",
    ]
    return "\n".join(lines) + "\n"


def format_bom(
    schematic: Schematic,
    fields: list[str] | None = None,
    fields_all: bool = False,
) -> str:
    sorted_comps = sorted(schematic.components, key=lambda c: c.reference)

    if fields_all:
        all_keys: dict[str, None] = {}
        for comp in sorted_comps:
            for key in comp.properties:
                all_keys[key] = None
        fields = list(all_keys)

    ref_width = max(len("Ref"), max((len(c.reference) for c in sorted_comps), default=0))
    val_width = max(len("Value"), max((len(c.value) for c in sorted_comps), default=0))
    fp_width = max(len("Footprint"), max((len(c.footprint) for c in sorted_comps), default=0))

    field_widths = []
    if fields:
        for f in fields:
            w = max(len(f), max((len(c.properties.get(f, "")) for c in sorted_comps), default=0))
            field_widths.append(w)

    header = f"{'Ref':<{ref_width}}  {'Value':<{val_width}}  {'Footprint':<{fp_width}}"
    if fields:
        for f, w in zip(fields, field_widths):
            header += f"  {f:<{w}}"
    lines = [header]

    for comp in sorted_comps:
        line = f"{comp.reference:<{ref_width}}  {comp.value:<{val_width}}  {comp.footprint:<{fp_width}}"
        if fields:
            for f, w in zip(fields, field_widths):
                line += f"  {comp.properties.get(f, ''):<{w}}"
        lines.append(line)

    return "\n".join(lines) + "\n"



def format_groups(groups: list[Group]) -> str:
    lines = []
    for group in groups:
        label = group.name or "(unlabeled)"
        lines.append(f"{label}: {', '.join(group.references)}")
    return "\n".join(lines) + "\n"


def _build_pin_index(nets: list[Net]) -> dict[tuple[str, str], list[tuple[Net, list[PinConnection]]]]:
    index: dict[tuple[str, str], list[tuple[Net, list[PinConnection]]]] = {}
    for net in nets:
        for conn in net.connections:
            key = (conn.component_ref, conn.pin_name)
            peers = [c for c in net.connections if c is not conn]
            index.setdefault(key, []).append((net, peers))
    return index


def _get_component_pins(
    ref: str,
    pin_to_nets: dict[tuple[str, str], list[tuple[Net, list[PinConnection]]]],
) -> list[tuple[str, Net, list[PinConnection]]]:
    results = []
    for (comp_ref, pin_name), entries in pin_to_nets.items():
        if comp_ref == ref:
            for net, peers in entries:
                results.append((pin_name, net, peers))
    return results


def _build_ref_to_group(groups: list[Group]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group in groups:
        if group.name:
            for ref in group.references:
                mapping[ref] = group.name
    return mapping


def _format_component_header(comp, group: str | None = None) -> str:
    parts = [comp.reference, comp.value, comp.footprint]
    if comp.properties:
        props = ", ".join(f"{k}: {v}" for k, v in comp.properties.items())
        parts.append("{" + props + "}")
    if group:
        parts.append(f"[{group}]")
    return "  ".join(parts)


def _format_pin_line(
    pin_name: str, net: Net, peers: list[PinConnection], own_ref: str
) -> str:
    if net.is_power:
        return f"  {pin_name}  <- {net.name}"

    peer_strs = [f"{p.component_ref}:{p.pin_name}" for p in peers]
    peer_part = ", ".join(peer_strs)

    parts = [f"  {pin_name}"]
    if peer_part:
        parts.append(f"-- {peer_part}")
    if net.name:
        parts.append(f"({net.name})")
    return "  ".join(parts)
