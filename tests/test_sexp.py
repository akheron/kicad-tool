from kicad_tool.sexp import parse_sexp, SexpNode


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
