import subprocess
import os
import shutil
import sys
import tempfile

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


def test_cli_set():
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    os.close(fd)
    shutil.copy2(HIRVI, path)
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "kicad_tool.cli",
                "set", path,
                "--ref", "C1",
                "--set", "Value=1000uF",
                "--set", "MPN=ECA-1VHG471",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Value" in result.stdout
        assert "MPN" in result.stdout

        # Verify file was actually modified
        from kicad_tool.sexp import SexpNode, parse_sexp
        with open(path) as f:
            data = parse_sexp(f.read())
        root = SexpNode(data)
        for sym in root.children("symbol"):
            for prop in sym.children("property"):
                if prop.value == "Reference" and str(prop.raw[2]) == "C1":
                    for p in SexpNode(sym.raw).children("property"):
                        if p.value == "Value":
                            assert str(p.raw[2]) == "1000uF"
                    break
    finally:
        os.unlink(path)


def test_cli_bom_fields():
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    os.close(fd)
    shutil.copy2(HIRVI, path)
    try:
        # First, add a custom property to a component
        subprocess.run(
            [
                sys.executable, "-m", "kicad_tool.cli",
                "set", path,
                "--ref", "C1",
                "--set", "LCSC=C12345",
            ],
            capture_output=True,
            text=True,
        )
        # Now run bom with --fields
        result = subprocess.run(
            [sys.executable, "-m", "kicad_tool.cli", "bom", path, "--fields", "LCSC"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "LCSC" in result.stdout
        assert "C12345" in result.stdout
    finally:
        os.unlink(path)


def test_cli_bom_fields_all():
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    os.close(fd)
    shutil.copy2(HIRVI, path)
    try:
        subprocess.run(
            [
                sys.executable, "-m", "kicad_tool.cli",
                "set", path,
                "--ref", "C1",
                "--set", "LCSC=C12345",
                "--set", "MF=SomeVendor",
            ],
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "kicad_tool.cli", "bom", path, "--fields-all"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "LCSC" in result.stdout
        assert "C12345" in result.stdout
        assert "MF" in result.stdout
        assert "SomeVendor" in result.stdout
    finally:
        os.unlink(path)


def test_cli_set_error_ref_not_found():
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    os.close(fd)
    shutil.copy2(HIRVI, path)
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "kicad_tool.cli",
                "set", path,
                "--ref", "ZZZZ99",
                "--set", "Value=foo",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr
    finally:
        os.unlink(path)
