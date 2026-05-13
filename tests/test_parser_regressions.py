import unittest

from minithon.icg import ICG, Quadruple
from minithon.lexer import tokenize
from minithon.parser.main import Parser


def compile_quads(source: str) -> list[Quadruple]:
    tokens, errors = tokenize(source)
    if errors:
        raise AssertionError(f"Unexpected lexer errors: {errors}")
    program = Parser(tokens, source).parse()
    return ICG().generate_quads(program, source)


class TestParserRegressions(unittest.TestCase):
    def test_and_comparison_precedence_in_while_condition(self) -> None:
        source = (
            "a = 1\n"
            "b = 2\n"
            "x = 3\n"
            "while a > 35 and b < x :\n"
            "    pass\n"
        )
        quads = compile_quads(source)
        expected = [
            Quadruple(":=", "a", "1", None),
            Quadruple(":=", "b", "2", None),
            Quadruple(":=", "x", "3", None),
            Quadruple("label", "L1", None, None),
            Quadruple(">", "t1", "a", "35"),
            Quadruple("<", "t2", "b", "x"),
            Quadruple("&&", "t3", "t1", "t2"),
            Quadruple("ifFalse", "L2", "t3", None),
            Quadruple("goto", "L1", None, None),
            Quadruple("label", "L2", None, None),
        ]
        self.assertEqual(quads, expected)


if __name__ == "__main__":
    unittest.main()

