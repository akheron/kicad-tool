# kicad-tool

CLI tool that extracts netlist connectivity and component properties from KiCad `.kicad_sch` schematic files into a compact text format for LLM consumption.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install kicad-tool --from .
```

## Usage

```bash
# Full netlist
kicad-tool netlist board.kicad_sch

# Filter by component reference
kicad-tool netlist board.kicad_sch --ref 'U1*'

# Filter by net name
kicad-tool netlist board.kicad_sch --net GND

# One-line-per-component summary
kicad-tool netlist board.kicad_sch --summary

# Bill of materials
kicad-tool bom board.kicad_sch

# Component groups from labeled rectangles
kicad-tool groups board.kicad_sch
```

## Disclaimer

This project was entirely vibe coded.
