import argparse
import sys
from fnmatch import fnmatch

from kicad_tool.parser import parse_schematic
from kicad_tool.formatter import format_bom, format_groups, format_netlist, format_summary


EXAMPLES = """\
Examples:
  kicad-tool netlist board.kicad_sch               full netlist
  kicad-tool netlist board.kicad_sch --ref 'U1*'   filter by reference
  kicad-tool netlist board.kicad_sch --summary     one-line-per-component summary
  kicad-tool bom board.kicad_sch                   bill of materials
  kicad-tool groups board.kicad_sch                component groups from labeled rectangles
"""


def main():
    parser = argparse.ArgumentParser(
        prog="kicad-tool",
        description="Extract netlist connectivity and component info from KiCad schematics.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    netlist_parser = subparsers.add_parser(
        "netlist",
        help="Show component connectivity and net assignments",
        description="Show per-component pin connections and net assignments. "
        "Use --ref and --net to narrow the output to a subset of components.",
    )
    netlist_parser.add_argument("schematic", help="Path to .kicad_sch file")
    netlist_parser.add_argument(
        "--ref", metavar="PATTERN", help="Filter by component reference (glob, e.g. 'U1*')"
    )
    netlist_parser.add_argument("--net", metavar="NAME", help="Filter by net name")
    netlist_parser.add_argument(
        "--summary", action="store_true", help="One-line-per-component summary instead of full netlist"
    )

    bom_parser = subparsers.add_parser(
        "bom",
        help="List components grouped by value",
        description="Print a bill of materials: components grouped by value with reference lists.",
    )
    bom_parser.add_argument("schematic", help="Path to .kicad_sch file")

    groups_parser = subparsers.add_parser(
        "groups",
        help="List component groups defined by labeled rectangles",
        description="Show components grouped by labeled rectangles drawn on the schematic. "
        "Requires the schematic to have rectangles with text labels near their top edge.",
    )
    groups_parser.add_argument("schematic", help="Path to .kicad_sch file")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    schematic = parse_schematic(args.schematic)

    if args.command == "groups":
        print(format_groups(schematic.groups), end="")
        return

    if args.command == "bom":
        print(format_bom(schematic), end="")
        return

    if args.summary:
        print(format_summary(schematic), end="")
        return

    components_filter = None
    if args.ref:
        matched = {c.reference for c in schematic.components if fnmatch(c.reference, args.ref)}
        if args.net:
            net_refs = set()
            for net in schematic.nets:
                if net.name == args.net:
                    net_refs.update(c.component_ref for c in net.connections)
            matched &= net_refs
        neighbors = set()
        for net in schematic.nets:
            refs_in_net = {c.component_ref for c in net.connections}
            if refs_in_net & matched:
                neighbors.update(refs_in_net)
        components_filter = matched | neighbors
    elif args.net:
        components_filter = set()
        for net in schematic.nets:
            if net.name == args.net:
                components_filter.update(c.component_ref for c in net.connections)

    print(format_netlist(schematic, components_filter=components_filter), end="")


if __name__ == "__main__":
    main()
