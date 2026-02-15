import subprocess
import os
import sys

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
HIRVI = os.path.join(FIXTURES, "hirvi.kicad_sch")


def test_cli_netlist():
    result = subprocess.run(
        [sys.executable, "-m", "kicad_tool.cli", "netlist", HIRVI],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "U1A" in result.stdout
    assert "M1" in result.stdout


def test_cli_summary():
    result = subprocess.run(
        [sys.executable, "-m", "kicad_tool.cli", "netlist", "--summary", HIRVI],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Components: 58" in result.stdout
    assert "Nets:" in result.stdout


def test_cli_filter_ref():
    result = subprocess.run(
        [sys.executable, "-m", "kicad_tool.cli", "netlist", "--ref", "Q1", HIRVI],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Q1" in result.stdout
    assert "IRF9Z34NPBF" in result.stdout


def test_cli_bom():
    result = subprocess.run(
        [sys.executable, "-m", "kicad_tool.cli", "bom", HIRVI],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Ref" in result.stdout
    assert "U1A" in result.stdout
    assert "R1" in result.stdout


def test_cli_groups():
    result = subprocess.run(
        [sys.executable, "-m", "kicad_tool.cli", "groups", HIRVI],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Inputs & protection:" in result.stdout
    assert "Motor H-bridge:" in result.stdout
    assert "D1" in result.stdout
