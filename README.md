# Minithon Compiler

A small, educational compiler front-end for a Python-like language ("Minithon").
Right now the project focuses on lexing/tokenization and error reporting, with
clear checkpoints for the next phases.

**Phase 1: Lexer (Current)**
- Regex-based tokenizer for Minithon source files
- Token types for keywords, operators, literals, and punctuation
- Error reporting with line/column highlighting for unrecognized tokens

**Phase 2: Parser (Planned)**
- Build an AST from the token stream
- Syntax error recovery and helpful diagnostics

**Phase 3: Semantic Analysis (Planned)**
- Name resolution and scope checks
- Type checks for expressions and statements

**Phase 4: IR / Code Generation (Planned)**
- Lower AST to a simple IR
- Prepare for bytecode or target backend

**Run Instructions**
1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the compiler entry point on a file (defaults to `minithon/test_code.mipy`):

```bash
python -m minithon
```

4. Run against a specific source file:

```bash
python -m minithon path/to/file.mipy
```

5. Run the lexer test helper (prints tokens and timing):

```bash
python minithon/test.py
```

**Project Layout**
- `minithon/lexer.py`: Token definitions and tokenizer
- `minithon/common.py`: Shared error formatting utilities
- `minithon/main.py`: CLI entry point
- `minithon/test_code.mipy`: Sample input

