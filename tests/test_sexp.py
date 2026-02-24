import os

from kicad_tool.sexp import parse_sexp, serialize_sexp, SexpNode, QuotedStr

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
HIRVI = os.path.join(FIXTURES, "hirvi.kicad_sch")


def test_parse_simple():
    result = parse_sexp("(hello world)")
    assert result == ["hello", "world"]


def test_parse_nested():
    result = parse_sexp("(a (b 1 2) (c 3))")
    assert result == ["a", ["b", 1, 2], ["c", 3]]


def test_parse_quoted_string():
    result = parse_sexp('(property "Reference" "U1")')
    assert result == ["property", "Reference", "U1"]


def test_parse_quoted_string_with_escapes():
    result = parse_sexp(r'(desc "says \"hello\"")')
    assert result == ["desc", 'says "hello"']


def test_parse_negative_numbers():
    result = parse_sexp("(at -5.08 0 180)")
    assert result == ["at", -5.08, 0, 180]


def test_parse_integers_and_floats():
    result = parse_sexp("(size 1.27 1.27)")
    assert result == ["size", 1.27, 1.27]


def test_sexpnode_tag():
    node = SexpNode(["symbol", "4xxx:40106", ["unit", 1]])
    assert node.tag == "symbol"


def test_sexpnode_value():
    node = SexpNode(["symbol", "4xxx:40106"])
    assert node.value == "4xxx:40106"


def test_sexpnode_values():
    node = SexpNode(["at", -5.08, 0, 180])
    assert node.values == [-5.08, 0, 180]


def test_sexpnode_child():
    node = SexpNode(["symbol", "foo", ["unit", 1], ["at", 0, 0]])
    assert node.child("unit").value == 1
    assert node.child("at").values == [0, 0]
    assert node.child("missing") is None


def test_sexpnode_children():
    node = SexpNode([
        "lib_symbols",
        ["symbol", "Device:R", ["pin", "1"]],
        ["symbol", "Device:C", ["pin", "2"]],
    ])
    syms = list(node.children("symbol"))
    assert len(syms) == 2
    assert syms[0].value == "Device:R"
    assert syms[1].value == "Device:C"


def test_sexpnode_has():
    node = SexpNode(["symbol", ["mirror", "x"], ["unit", 1]])
    assert node.has("mirror")
    assert not node.has("rotation")


def test_sexpnode_raw():
    data = ["pin", "input", "line", ["at", 0, 0]]
    node = SexpNode(data)
    assert node.raw is data
    assert node.raw[1] == "input"


def test_parse_real_wire():
    text = '(wire (pts (xy 383.54 57.15) (xy 383.54 45.72)) (stroke (width 0) (type default)) (uuid "abc"))'
    node = SexpNode(parse_sexp(text))
    pts = list(node.child("pts").children("xy"))
    assert pts[0].values == [383.54, 57.15]
    assert pts[1].values == [383.54, 45.72]


def test_parse_real_label():
    text = '(label "ON" (at 243.84 212.09 0) (effects (font (size 1.27 1.27))) (uuid "abc"))'
    node = SexpNode(parse_sexp(text))
    assert node.value == "ON"
    assert node.child("at").values == [243.84, 212.09, 0]


def test_quoted_str_is_str():
    q = QuotedStr("hello")
    assert isinstance(q, str)
    assert q == "hello"
    assert str(q) == "hello"


def test_quoted_str_isinstance():
    q = QuotedStr("hello")
    assert isinstance(q, QuotedStr)
    plain = "hello"
    assert not isinstance(plain, QuotedStr)


def test_atom_returns_quoted_str_for_quoted_tokens():
    result = parse_sexp('(property "Reference" "U1")')
    assert isinstance(result[1], QuotedStr)
    assert isinstance(result[2], QuotedStr)
    assert result[1] == "Reference"
    assert result[2] == "U1"


def test_atom_returns_plain_str_for_unquoted_tokens():
    result = parse_sexp("(hide yes)")
    assert isinstance(result[1], str)
    assert not isinstance(result[1], QuotedStr)
    assert result[1] == "yes"


def test_serialize_inline_atoms():
    data = ["at", 1.27, 0, 180]
    assert serialize_sexp(data) == "(at 1.27 0 180)\n"


def test_serialize_quoted_strings():
    data = ["property", QuotedStr("Reference"), QuotedStr("U1")]
    assert serialize_sexp(data) == '(property "Reference" "U1")\n'


def test_serialize_unquoted_keyword():
    data = ["hide", "yes"]
    assert serialize_sexp(data) == "(hide yes)\n"


def test_serialize_multiline():
    data = ["font", ["size", 1.27, 1.27]]
    expected = "(font\n\t(size 1.27 1.27)\n)\n"
    assert serialize_sexp(data) == expected


def test_serialize_nested():
    data = [
        "property", QuotedStr("Value"), QuotedStr("40106"),
        ["at", 0, 0, 0],
        ["effects",
            ["font",
                ["size", 1.27, 1.27],
            ],
            ["hide", "yes"],
        ],
    ]
    expected = (
        '(property "Value" "40106"\n'
        "\t(at 0 0 0)\n"
        "\t(effects\n"
        "\t\t(font\n"
        "\t\t\t(size 1.27 1.27)\n"
        "\t\t)\n"
        "\t\t(hide yes)\n"
        "\t)\n"
        ")\n"
    )
    assert serialize_sexp(data) == expected


def test_serialize_string_with_special_chars():
    data = ["desc", QuotedStr('says "hello"')]
    assert serialize_sexp(data) == '(desc "says \\"hello\\"")\n'


def test_serialize_float_formatting():
    data = ["at", 217.17, 78.74, 0]
    assert serialize_sexp(data) == "(at 217.17 78.74 0)\n"


def test_serialize_negative_numbers():
    data = ["at", -5.08, 0, 180]
    assert serialize_sexp(data) == "(at -5.08 0 180)\n"


def test_serialize_roundtrip_hirvi():
    """Parse hirvi.kicad_sch, serialize, re-parse — data structures must match."""
    with open(HIRVI) as f:
        text = f.read()
    data = parse_sexp(text)
    serialized = serialize_sexp(data)
    reparsed = parse_sexp(serialized)
    assert data == reparsed
