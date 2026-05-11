import unittest

from minithon.icg import ICG, Quadruple, RuntimeError
from minithon.lexer import tokenize
from minithon.parser.main import Parser


def compile_quads(source: str) -> list[Quadruple]:
    tokens, errors = tokenize(source)
    if errors:
        raise AssertionError(f"Unexpected lexer errors: {errors}")
    program = Parser(tokens, source).parse()
    return ICG().generate_quads(program, source)


class TestICGQuadruples(unittest.TestCase):
    def test_while_generates_expected_quads(self) -> None:
        source = "a = 2\nwhile a > 35 :\n    b = a + 1\n"
        quads = compile_quads(source)
        expected = [
            Quadruple(":=", "a", "2", None),
            Quadruple("label", "L1", None, None),
            Quadruple(">", "t1", "a", "35"),
            Quadruple("ifFalse", "L2", "t1", None),
            Quadruple("+", "t2", "a", "1"),
            Quadruple(":=", "b", "t2", None),
            Quadruple("goto", "L1", None, None),
            Quadruple("label", "L2", None, None),
        ]
        self.assertEqual(quads, expected)

    def test_if_elif_else_generates_expected_quads(self) -> None:
        source = (
            "a = 1\n"
            "if a > 0 :\n"
            "    b = 2\n"
            "elif a == 0 :\n"
            "    b = 3\n"
            "else :\n"
            "    b = 4\n"
        )
        quads = compile_quads(source)
        expected = [
            Quadruple(":=", "a", "1", None),
            Quadruple(">", "t1", "a", "0"),
            Quadruple("ifFalse", "L2", "t1", None),
            Quadruple(":=", "b", "2", None),
            Quadruple("goto", "L1", None, None),
            Quadruple("label", "L2", None, None),
            Quadruple("==", "t2", "a", "0"),
            Quadruple("ifFalse", "L3", "t2", None),
            Quadruple(":=", "b", "3", None),
            Quadruple("goto", "L1", None, None),
            Quadruple("label", "L3", None, None),
            Quadruple(":=", "b", "4", None),
            Quadruple("label", "L1", None, None),
        ]
        self.assertEqual(quads, expected)

    def test_undefined_variable_in_else_branch_is_detected(self) -> None:
        source = (
            "a = 2\n"
            "while a > 35 :\n"
            "    if a > 10:\n"
            "        b = a + 1\n"
            "    else:\n"
            "        if b < 3:\n"
            "            pass\n"
        )
        with self.assertRaises(RuntimeError):
            compile_quads(source)


if __name__ == "__main__":
    unittest.main()
