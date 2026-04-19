from pathlib import Path
import argparse

from minithon.lexer import tokenize
from minithon.parser.main import Parser

def print_tokens_table(tokens: list, source_code: str) -> None:
    headers = ("Line", "Position", "Lexeme", "Tokentype")
    rows: list[tuple[str, str, str, str]] = []

    for token in tokens:
        line = str(source_code.count("\n", 0, token.position) + 1)
        rows.append((line, str(token.position), repr(token.lexeme), token.type.name))

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def fmt(row: tuple[str, str, str, str]) -> str:
        return " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))

    print(fmt(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(fmt(row))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Minithon source to IR")
    parser.add_argument("source", nargs="?", default=None, help="Path to .mipy file")

    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Print lexer tokens only and skip parsing/code generation",
    )
    parser.add_argument(
        "--parse-tree",
        action="store_true",
        help="Print parse tree before intermediate code",
    )
    args = parser.parse_args()

    source_path = (
        Path(args.source) if args.source is not None else Path(__file__).parent / "test_code.mipy"
    )
    source_code = source_path.read_text(encoding="utf-8")
    tokens, errors = tokenize(source_code)
    
    if errors:
        for err in errors:
            print(err)
        raise SystemExit(1)
    
    if args.tokens:
        print_tokens_table(tokens, source_code)
        return
    
    program = Parser(tokens, source_code).parse()
    if args.parse_tree:
        program.print_parse_tree()

if __name__ == "__main__":
    main()
