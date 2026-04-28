from pathlib import Path
import argparse

from minithon.lexer import tokenize, Token
from minithon.parser.main import Parser

def format_lexeme(lexeme: str) -> str:
    return repr(lexeme)

def format_tokens_table(tokens: list[Token]) -> str:
    headers = ("Lexeme", "Token Type", "Pattern", "Position")
    rows = [
        (
            format_lexeme(token.lexeme),
            token.type.name,
            token.type.value,
            str(token.position),
        )
        for token in tokens
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in rows)) if rows else len(header)
        for index, header in enumerate(headers)
    ]

    def format_row(row: tuple[str, str, str, str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    lines = [format_row(headers), separator]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)



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
        print(format_tokens_table(tokens))
        # return
    
    program = Parser(tokens, source_code).parse()
    if args.parse_tree:
        program.print_parse_tree()

if __name__ == "__main__":
    main()
