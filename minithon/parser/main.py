from typing import NoReturn

from minithon.lexer import Token, TokenType
from minithon.parser.types import (
    AssignmentStatement,
    Block,
    ControlFlowStmtBlock,
    ExprType,
    Expression,
    GenericStatement,
    IfStatementBlock,
    Program,
    StatementType,
    SyntaxError,
    UnaryExpression,
)


class Parser:
    def __init__(self, tokens: list[Token], source_code: str) -> None:
        self.tokens = tokens
        self.source_code = source_code
        self.token_index = 0
        self.block_id = 0

    def parse(self) -> Program:
        while self.match(TokenType.NEWLINE) is not None:
            pass
        statements = self.statement_list(stop_tokens={TokenType.EOF}, indent=0)
        self.expect(TokenType.EOF, "Expected end of file")
        return Program(self.new_block(statements, indent=0))

    def new_block(self, statements: list[StatementType], indent: int) -> Block:
        self.block_id += 1
        return Block(statements, self.block_id, indent)

    def raise_syntax_error(self, msg: str, token: Token | None = None) -> NoReturn:
        err_token = token if token is not None else self.peek(skip_comments=True)
        raise SyntaxError(
            msg,
            self.source_code,
            err_token.position,
            print_token=err_token.type != TokenType.EOF,
        )

    def peek(self, skip_comments: bool = True) -> Token:
        idx = self.token_index
        while (
            skip_comments
            and idx < len(self.tokens)
            and self.tokens[idx].type == TokenType.COMMENT
        ):
            idx += 1
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self, skip_comments: bool = True) -> Token:
        token = self.peek(skip_comments=skip_comments)
        if skip_comments:
            while (
                self.token_index < len(self.tokens)
                and self.tokens[self.token_index].type == TokenType.COMMENT
            ):
                self.token_index += 1
        if self.token_index < len(self.tokens):
            self.token_index += 1
        return token

    def match(self, token_type: TokenType) -> Token | None:
        token = self.peek(skip_comments=True)
        if token.type != token_type:
            return None
        return self.advance(skip_comments=True)

    def expect(self, token_type: TokenType, msg: str) -> Token:
        token = self.match(token_type)
        if token is None:
            found = self.peek(skip_comments=True).type.name
            self.raise_syntax_error(f"{msg} (found {found}, expected {token_type.name})")
        return token

    def is_statement_start(self, token_type: TokenType) -> bool:
        return token_type in (
            TokenType.IDENTIFIER,
            TokenType.IF,
            TokenType.WHILE,
            TokenType.PASS,
            TokenType.BREAK,
            TokenType.CONTINUE,
        )

    # P -> SL EOF
    # SL -> S SL_TAIL
    # SL_TAIL -> S SL_TAIL | epsilon
    def statement_list(
        self, stop_tokens: set[TokenType], indent: int
    ) -> list[StatementType]:
        statements: list[StatementType] = []
        while True:
            lookahead = self.peek(skip_comments=True)
            if lookahead.type in stop_tokens:
                break
            if not self.is_statement_start(lookahead.type):
                self.raise_syntax_error("Expected statement", lookahead)
            statements.append(self.statement(indent))

        if not statements:
            self.raise_syntax_error("Expected statement", self.peek(skip_comments=True))

        return statements

    # S -> SIMPLE NEWLINE | COMPOUND
    # SIMPLE -> AS | pass | break | continue
    # COMPOUND -> IS | WS
    def statement(self, indent: int) -> StatementType:
        lookahead = self.peek(skip_comments=True).type
        if lookahead == TokenType.IF:
            return self.if_statement(indent)
        if lookahead == TokenType.WHILE:
            return self.while_statement(indent)

        stmt: StatementType
        if lookahead == TokenType.IDENTIFIER:
            stmt = self.assignment_statement()
        elif lookahead == TokenType.PASS:
            stmt = GenericStatement(self.advance(), "PASS")
        elif lookahead == TokenType.BREAK:
            stmt = GenericStatement(self.advance(), "BREAK")
        elif lookahead == TokenType.CONTINUE:
            stmt = GenericStatement(self.advance(), "CONTINUE")
        else:
            self.raise_syntax_error("Expected statement")

        # Simple statements should end with NEWLINE. We also allow implicit
        # line termination before DEDENT/EOF for files without trailing newline.
        if self.match(TokenType.NEWLINE) is None:
            next_type = self.peek(skip_comments=True).type
            if next_type not in (TokenType.DEDENT, TokenType.EOF):
                self.raise_syntax_error(
                    "Expected newline after simple statement",
                    self.peek(skip_comments=True),
                )
        return stmt

    # AS -> id = E
    def assignment_statement(self) -> AssignmentStatement:
        identifier = self.expect(TokenType.IDENTIFIER, "Expected identifier")
        self.expect(TokenType.ASSIGN, "Expected assignment operator")
        expression = self.expression()
        return AssignmentStatement(identifier, expression)

    # B -> NEWLINE INDENT SL DEDENT
    def block(self, indent: int) -> Block:
        self.expect(TokenType.NEWLINE, "Expected newline before block")
        self.expect(TokenType.INDENT, "Expected INDENT to start block")
        statements = self.statement_list(stop_tokens={TokenType.DEDENT}, indent=indent)
        self.expect(TokenType.DEDENT, "Expected DEDENT to close block")
        return self.new_block(statements, indent=indent)

    # IS -> if E : B IS'
    # IS' -> elif E : B IS' | else : B | epsilon
    def if_statement(self, indent: int) -> IfStatementBlock:
        if_token = self.expect(TokenType.IF, "Expected IF")
        if_expr = self.expression()
        self.expect(TokenType.COLON, "Expected ':' after if condition")
        if_block = self.block(indent + 1)
        if_stmt = ControlFlowStmtBlock(if_token, if_expr, if_block)

        elif_blocks: list[ControlFlowStmtBlock] = []
        while self.peek(skip_comments=True).type == TokenType.ELIF:
            elif_token = self.advance()
            elif_expr = self.expression()
            self.expect(TokenType.COLON, "Expected ':' after elif condition")
            elif_block = self.block(indent + 1)
            elif_blocks.append(ControlFlowStmtBlock(elif_token, elif_expr, elif_block))

        else_block: ControlFlowStmtBlock | None = None
        if self.peek(skip_comments=True).type == TokenType.ELSE:
            else_token = self.advance()
            self.expect(TokenType.COLON, "Expected ':' after else")
            parsed_block = self.block(indent + 1)
            else_block = ControlFlowStmtBlock(else_token, None, parsed_block)

        return IfStatementBlock(if_stmt, elif_blocks, else_block)

    # WS -> while E : B
    def while_statement(self, indent: int) -> ControlFlowStmtBlock:
        while_token = self.expect(TokenType.WHILE, "Expected WHILE")
        expression = self.expression()
        self.expect(TokenType.COLON, "Expected ':' after while condition")
        parsed_block = self.block(indent + 1)
        return ControlFlowStmtBlock(while_token, expression, parsed_block)

    # E -> OrExpr | string
    def expression(self) -> ExprType:
        if self.peek(skip_comments=True).type == TokenType.STRING:
            return Expression(self.advance())
        return self.or_expr()

    # OrExpr -> AndExpr OrExpr'
    # OrExpr' -> or AndExpr OrExpr' | epsilon
    def or_expr(self) -> ExprType:
        left = self.and_expr()
        while True:
            op = self.match(TokenType.OR)
            if op is None:
                break
            right = self.and_expr()
            left = Expression(left, op, right)
        return left

    # AndExpr -> NotExpr AndExpr'
    # AndExpr' -> and NotExpr AndExpr' | epsilon
    def and_expr(self) -> ExprType:
        left = self.not_expr()
        while True:
            op = self.match(TokenType.AND)
            if op is None:
                break
            right = self.not_expr()
            left = Expression(left, op, right)
        return left

    # NotExpr -> not NotExpr | CompExpr | True | False
    def not_expr(self) -> ExprType:
        op = self.match(TokenType.NOT)
        if op is not None:
            right = self.not_expr()
            return UnaryExpression(op, right)

        bool_true = self.match(TokenType.BOOL_TRUE)
        if bool_true is not None:
            return Expression(bool_true)

        bool_false = self.match(TokenType.BOOL_FALSE)
        if bool_false is not None:
            return Expression(bool_false)

        return self.comp_expr()

    # CompExpr -> AE CompExpr'
    # CompExpr' -> RO AE CompExpr' | epsilon
    def comp_expr(self) -> ExprType:
        left = self.arithmetic_expr()
        while self.peek(skip_comments=True).type in (
            TokenType.EQUAL,
            TokenType.NOT_EQUAL,
            TokenType.LESS_THAN,
            TokenType.GREATER_THAN,
            TokenType.LESS_THAN_OR_EQUAL,
            TokenType.GREATER_THAN_OR_EQUAL,
        ):
            op = self.advance()
            right = self.arithmetic_expr()
            left = Expression(left, op, right)
        return left

    # AE -> T AE'
    # AE' -> + T AE' | - T AE' | epsilon
    def arithmetic_expr(self) -> ExprType:
        left = self.term()
        while self.peek(skip_comments=True).type in (TokenType.ADD, TokenType.SUBTRACT):
            op = self.advance()
            right = self.term()
            left = Expression(left, op, right)
        return left

    # T -> F T'
    # T' -> * F T' | / F T' | % F T' | epsilon
    def term(self) -> ExprType:
        left = self.factor()
        while self.peek(skip_comments=True).type in (
            TokenType.MULTIPLY,
            TokenType.DIVIDE,
            TokenType.MODULUS,
        ):
            op = self.advance()
            right = self.factor()
            left = Expression(left, op, right)
        return left

    # F -> id | int | float | ( E )
    def factor(self) -> ExprType:
        token_type = self.peek(skip_comments=True).type
        if token_type in (TokenType.IDENTIFIER, TokenType.INTEGER, TokenType.FLOAT):
            return Expression(self.advance())

        if self.match(TokenType.LPAREN) is not None:
            expr = self.expression()
            self.expect(TokenType.RPAREN, "Expected closing parenthesis")
            return expr

        self.raise_syntax_error(
            "Expected identifier, number, or parenthesized expression",
            self.peek(skip_comments=True),
        )
