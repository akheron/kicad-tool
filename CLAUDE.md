# kicad-tool

CLI tool that extracts netlist connectivity and component properties from KiCad `.kicad_sch` files into a compact text format for LLM consumption.

## Architecture

Three-layer pipeline: parser → data model → formatter, wired together by the CLI.

- `src/kicad_tool/models.py` — Dataclasses: `Component`, `PinConnection`, `Net`, `Schematic`
- `src/kicad_tool/parser.py` — Loads `.kicad_sch` via `kicad-skip`, builds nets using coordinate-based union-find
- `src/kicad_tool/formatter.py` — Renders component-centric adjacency text (`format_netlist`, `format_summary`, `format_bom`, `format_groups`)
- `src/kicad_tool/cli.py` — Argparse CLI with `netlist`, `bom`, `groups` subcommands

## Dependencies

- `kicad-skip` — KiCad S-expression schematic parsing
- `pytest` — testing (dev dependency)

## Running commands

All commands must be run through `uv run` from the project root:

```bash
uv run pytest tests/ -v          # run all tests
uv run pytest tests/test_foo.py  # run specific test file
uv run kicad-tool --help         # run the CLI
```

Do NOT run `pytest` or `kicad-tool` directly — they won't find the virtualenv or dependencies.

## Git

Always run `git` without the `-C` flag so that sandbox allow rules work correctly. Use the working directory instead.

## Testing

Test fixtures live in `tests/fixtures/`. The `hirvi.kicad_sch` fixture is a real KiCad schematic with multi-unit ICs (40106, 4013, 4071, 4081), an H-bridge motor driver, switches, and global/power labels.

Tests cover: data model, formatter output (netlist, BOM, clusters), parser extraction (per-unit components, power nets, pin names, connectivity), analyzer (clustering), CLI integration (via subprocess).
