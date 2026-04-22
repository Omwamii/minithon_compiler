from typing import NoReturn
from minithon.lexer import Token, TokenType
from minithon.parser.types import (
    Node,
    Expression,
    ControlFlowStmtBlock,
    IfStatementBlock,
    GenericStatement,
    AssignmentStatement,
    StatementType,
    Block,
    Program,
    SyntaxError,
)


class Parser:
    def __init__(self, tokens: list[Token], source_code: str) -> None:
        self.tokens = tokens
        self.current_token: Token
        self.token_index = -1
        self.current_node: Node
        self.source_code = source_code
        self.block_id = 0
        self.indent_level = 0

    def raise_syntax_error(
        self,
        msg: str,
        position: int | None = None,
        ignore_newline: bool = False,
        ignore_whitespace: bool = True,
        print_token: bool = True,
    ) -> NoReturn:
        if position is None:
            error_position = self.lookahead_position(ignore_newline, ignore_whitespace)
        else:
            error_position = position
        raise SyntaxError(msg, self.source_code, error_position, print_token=print_token)

    def raise_unexpected_token(
        self, expected: str, token: Token | None = None
    ) -> NoReturn:
        observed_token = token if token is not None else self.lookahead_token()
        observed = observed_token.lexeme if observed_token is not None else "EOF"
        position = observed_token.position if observed_token is not None else None
        self.raise_syntax_error(
            f'Unexpected token "{observed}" expected "{expected}"',
            position=position,
            print_token=False,
        )

    def lookahead_position(
        self, ignore_newline=True, ignore_whitespace=True
    ) -> int:
        lookahead_index = self.token_index + 1
        while lookahead_index < len(self.tokens):
            token = self.tokens[lookahead_index]
            if (
                token.type == TokenType.COMMENT
                or (ignore_newline and token.type == TokenType.NEWLINE)
                or (ignore_whitespace and token.type == TokenType.WHITESPACE)
            ):
                lookahead_index += 1
                continue
            return token.position
        if self.token_index >= 0:
            return self.current_token.position
        return 0

    def lookahead_token(
        self, ignore_newline=True, ignore_whitespace=True
    ) -> Token | None:
        lookahead_index = self.token_index + 1
        while lookahead_index < len(self.tokens):
            token = self.tokens[lookahead_index]
            if (
                token.type == TokenType.COMMENT
                or (ignore_newline and token.type == TokenType.NEWLINE)
                or (ignore_whitespace and token.type == TokenType.WHITESPACE)
            ):
                lookahead_index += 1
                continue
            return token
        return None

    def parse(self) -> Program:
        return self.program()

    def program(self) -> Program:
        while self.match(TokenType.NEWLINE, False, False):
            pass
        statements = self.statement_list({TokenType.EOF})
        if not statements:
            self.raise_syntax_error("Expected statement")
        if not self.match(TokenType.EOF):
            self.raise_unexpected_token("EOF")
        return Program(self.new_block(statements, 0))

    def new_block(self, statements: list[StatementType], indent: int) -> Block:
        self.block_id += 1
        return Block(statements, self.block_id, indent)

    def statement_list(self, stop_tokens: set[TokenType]) -> list[StatementType]:
        statements: list[StatementType] = []
        while True:
            lookahead = self.lookahead_token(ignore_newline=False, ignore_whitespace=False)
            if lookahead is None or lookahead.type in stop_tokens:
                break
            statement = self.statement()
            if statement is None:
                if (
                    TokenType.DEDENT in stop_tokens
                    and lookahead.type in (TokenType.ELSE, TokenType.ELIF)
                ):
                    self.raise_unexpected_token("DEDENT", lookahead)
                self.raise_unexpected_token("statement", lookahead)
            statements.append(statement)

        return statements

    def match(
        self, token_type: TokenType, ignore_newline=True, ignore_whitespace=True
    ) -> bool:
        if self.token_index + 1 >= len(self.tokens):
            return False
        self.token_index += 1
        self.current_token = self.tokens[self.token_index]
        matched = False
        if (
            self.current_token.type == TokenType.COMMENT
            or (ignore_newline and self.current_token.type == TokenType.NEWLINE)
            or (ignore_whitespace and self.current_token.type == TokenType.WHITESPACE)
        ):
            matched = self.match(token_type, ignore_newline, ignore_whitespace)

        else:
            matched = self.current_token.type == token_type
        if matched:
            return True
        self.token_index -= 1
        self.current_token = self.tokens[self.token_index]
        return False

    def generic_statement(
        self, token_type: TokenType, string_repr: str
    ) -> GenericStatement | None:
        if not self.match(token_type):
            return None
        stmt = GenericStatement(self.current_token, string_repr)
        return stmt

    def statement(self) -> StatementType | None:
        statement = (
            self.generic_statement(TokenType.BREAK, "BREAK")
            or self.generic_statement(TokenType.CONTINUE, "CONTINUE")
            or self.generic_statement(TokenType.PASS, "PASS")
            or self.generic_statement(TokenType.COMMENT, "COMMENT")
            or self.assignment_statement()
        )
        if statement is not None:
            if not self.match(TokenType.NEWLINE, False):
                lookahead = self.lookahead_token(ignore_newline=False)
                if lookahead is None or lookahead.type not in (
                    TokenType.DEDENT,
                    TokenType.EOF,
                ):
                    self.raise_syntax_error("Expected newline")
            return statement
        statement = self.while_statement_block() or self.if_statement_block()
        return statement

    def assignment_statement(self) -> AssignmentStatement | None:
        if not self.match(TokenType.IDENTIFIER):
            return None
        identifier = self.current_token
        if not self.match(TokenType.ASSIGN):
            self.raise_syntax_error("Expected assignment operator")

        expression = self.expression()
        if expression is None:
            self.raise_syntax_error("Expected expression")
        stmt = AssignmentStatement(identifier, expression)
        return stmt

    def block(self) -> Block:
        if not self.match(TokenType.NEWLINE, False):
            self.raise_syntax_error("Expected newline")
        if not self.match(TokenType.INDENT, False):
            self.raise_syntax_error("Expected INDENT")

        self.indent_level += 1
        statements = self.statement_list({TokenType.DEDENT})
        if not statements:
            self.raise_syntax_error("Expected statement in block")
        if not self.match(TokenType.DEDENT, False):
            self.raise_syntax_error("Expected DEDENT")
        block = self.new_block(statements, self.indent_level)
        self.indent_level -= 1
        return block

    def control_flow_stmt_block(
        self, token_type: TokenType, has_expression=True
    ) -> ControlFlowStmtBlock | None:
        if not self.match(token_type):
            return None
        token = self.current_token
        expression: Expression | None = None
        if has_expression:
            expression = self.expression()
            if expression is None:
                self.raise_syntax_error("Expected expression")
        if not self.match(TokenType.COLON):
            self.raise_syntax_error("Expected colon")
        block = self.block()
        stmt_block = ControlFlowStmtBlock(token, expression, block)
        return stmt_block

    def if_statement_block(self) -> IfStatementBlock | None:
        if_stmt_block = self.control_flow_stmt_block(TokenType.IF)
        if if_stmt_block is None:
            return None
        elifs: list[ControlFlowStmtBlock] = []
        elif_stmt_block = self.control_flow_stmt_block(TokenType.ELIF)
        while elif_stmt_block is not None:
            elifs.append(elif_stmt_block)
            elif_stmt_block = self.control_flow_stmt_block(TokenType.ELIF)
        else_stmt_block = self.control_flow_stmt_block(TokenType.ELSE, False)
        statement_block = IfStatementBlock(if_stmt_block, elifs, else_stmt_block)
        return statement_block

    def while_statement_block(self) -> ControlFlowStmtBlock | None:
        stmt_block = self.control_flow_stmt_block(TokenType.WHILE)
        return stmt_block

    def factor(self) -> bool:
        return (
            self.match(TokenType.BOOL_TRUE, False)
            or self.match(TokenType.BOOL_FALSE, False)
            or self.match(TokenType.IDENTIFIER, False)
            or self.match(TokenType.STRING, False)
            or self.match(TokenType.INTEGER, False)
            or self.match(TokenType.FLOAT, False)
        )

    def expression(self) -> Expression | None:
        def match_ops() -> bool:
            return (
                self.match(TokenType.OR, False)
                or self.match(TokenType.AND, False)
                or self.match(TokenType.NOT, False)
                or self.match(TokenType.DIVIDE, False)
                or self.match(TokenType.MULTIPLY, False)
                or self.match(TokenType.ADD, False)
                or self.match(TokenType.SUBTRACT, False)
                or self.match(TokenType.EQUAL, False)
                or self.match(TokenType.NOT_EQUAL, False)
                or self.match(TokenType.MODULUS, False)
                or self.match(TokenType.GREATER_THAN, False)
                or self.match(TokenType.LESS_THAN, False)
                or self.match(TokenType.GREATER_THAN_OR_EQUAL, False)
                or self.match(TokenType.LESS_THAN_OR_EQUAL, False)
            )

        left_operand: Expression | Token
        if self.match(TokenType.LPAREN, False):
            expression = self.expression()
            if expression is None:
                self.raise_syntax_error("Expected expression")
            left_operand = expression
            if not self.match(TokenType.RPAREN, False):
                self.raise_syntax_error("Expected closing paranthesis")
        else:
            if not self.factor():
                return None
            left_operand = self.current_token
        operator = None
        right_operand = None
        if match_ops():
            operator = self.current_token
            right_operand = self.expression()
            if right_operand is None:
                self.raise_syntax_error("Expected expression")
        expression = Expression(left_operand, operator, right_operand)
        return expression
