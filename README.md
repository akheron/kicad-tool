# kicad-tool

CLI tool that extracts netlist connectivity and component properties from KiCad `.kicad_sch` schematic files into a compact text format for LLM consumption.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install kicad-tool --from .
```

## Usage

### Ref patterns

The `--ref` flag accepts comma-separated glob patterns and works across `netlist`, `bom`, and `set`:

```
U1         exact match
U*         glob wildcard
U*,R*      comma-separated patterns (matches all U and R refs)
```

### Netlist

```bash
kicad-tool netlist board.kicad_sch               # full netlist
kicad-tool netlist board.kicad_sch --ref 'U1*'   # filter by reference glob
kicad-tool netlist board.kicad_sch --ref 'U*,R*' # multiple patterns
kicad-tool netlist board.kicad_sch --net GND      # filter by net name
kicad-tool netlist board.kicad_sch --summary      # one-line-per-component summary
```

### Bill of materials

```bash
kicad-tool bom board.kicad_sch                   # full BOM
kicad-tool bom board.kicad_sch --ref 'R*'        # BOM filtered by reference
kicad-tool bom board.kicad_sch --fields LCSC,MF  # BOM with custom fields
kicad-tool bom board.kicad_sch --fields-all      # BOM with all custom fields
```

### Edit component properties

```bash
kicad-tool set board.kicad_sch --ref U1 --set Value=40106B    # edit a property
kicad-tool set board.kicad_sch --ref 'R*' --set MPN=RC0402    # batch edit
```

### Component groups

```bash
kicad-tool groups board.kicad_sch                # groups from labeled rectangles
```

## Disclaimer

This project was entirely vibe coded.
