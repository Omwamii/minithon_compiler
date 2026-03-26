from pathlib import Path
import argparse
from pprint import pprint

from minithon.lexer import tokenize


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile Minithon source to IR")
    parser.add_argument("source", nargs="?", default=None, help="Path to .mipy file")
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
    
    pprint(tokens)
    return


if __name__ == "__main__":
    main()