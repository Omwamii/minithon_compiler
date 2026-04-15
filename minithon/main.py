from pathlib import Path
import argparse
from pprint import pprint

from minithon.lexer import tokenize
from minithon.parser.main import Parser

def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Minithon source to IR")
    parser.add_argument("source", nargs="?", default=None, help="Path to .mipy file")
    args = parser.parse_args()

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
        pprint(tokens)
        return
    
    program = Parser(tokens, source_code).parse()
    if args.parse_tree:
        program.print_parse_tree()

if __name__ == "__main__":
    main()