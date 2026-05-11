from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from minithon.common import CommonException
from minithon.lexer import Token, TokenType
from minithon.parser.types import (
    AssignmentStatement,
    Block,
    ControlFlowStmtBlock,
    Expression,
    GenericStatement,
    IfStatementBlock,
    Program,
    UnaryExpression,
)


class RuntimeError(CommonException):
    def __init__(
        self, msg: str, source_code: str, position: int, print_token=True
    ) -> None:
        super().__init__(msg, source_code, position, print_token)


@dataclass(frozen=True, slots=True)
class Quadruple:
    op: str
    result: str | None = None
    arg1: str | None = None
    arg2: str | None = None


class ICG:
    def __init__(self) -> None:
        self.quads: list[Quadruple] = []
        self.temp_count = 0
        self.label_count = 0
        self.loop_stack: list[tuple[str, str]] = []
        self.defined_vars: set[str] = set()
        self.source_code: str

    def generate(self, program: Program, source_code: str) -> str:
        quads = self.generate_quads(program, source_code)
        return self.format_quads(quads)

    def generate_quads(self, program: Program, source_code: str) -> list[Quadruple]:
        self.quads = []
        self.temp_count = 0
        self.label_count = 0
        self.loop_stack = []
        self.defined_vars = set()
        self.source_code = source_code
        if program.block is None:
            return self.quads
        self.block(program.block)
        return self.quads

    def format_quads(self, quads: list[Quadruple]) -> str:
        lines: list[str] = []
        for index, q in enumerate(quads, start=1):
            res = "" if q.result is None else q.result
            a1 = "" if q.arg1 is None else q.arg1
            a2 = "" if q.arg2 is None else q.arg2
            lines.append(f"{index:d}: ({q.op}, {res}, {a1}, {a2})")
        return "\n".join(lines)

    def block(self, block: Block) -> None:
        for stmt in block.statements:
            if isinstance(stmt, AssignmentStatement):
                self.assignment_stmt(stmt)
            elif isinstance(stmt, IfStatementBlock):
                self.if_stmt(stmt)
            elif isinstance(stmt, ControlFlowStmtBlock):
                self.while_stmt(stmt)
            else:
                self.generic_stmt(stmt)

    def generic_stmt(
        self,
        stmt: GenericStatement,
    ) -> None:
        if not self.loop_stack:
            return
        continue_label, break_label = self.loop_stack[-1]
        if stmt.token.type == TokenType.CONTINUE:
            self.emit("goto", result=continue_label)
        elif stmt.token.type == TokenType.BREAK:
            self.emit("goto", result=break_label)

    def while_stmt(self, stmt: ControlFlowStmtBlock) -> None:
        start_label = self.get_label()
        exit_label = self.get_label()
        self.emit("label", result=start_label)

        stmt.expression = cast(Expression, stmt.expression)
        cond = self.expression_temp(stmt.expression)
        self.emit("ifFalse", arg1=cond, result=exit_label)

        self.loop_stack.append((start_label, exit_label))
        try:
            self.block(stmt.block)
        finally:
            self.loop_stack.pop()

        self.emit("goto", result=start_label)
        self.emit("label", result=exit_label)

    def if_stmt(self, stmt: IfStatementBlock) -> None:
        exit_label = self.get_label()
        next_test_label: str | None = None

        branches: list[ControlFlowStmtBlock] = [
            stmt.if_statement,
            *stmt.elif_statements,
        ]
        for branch in branches:
            if next_test_label is not None:
                self.emit("label", result=next_test_label)

            next_test_label = self.get_label()
            branch.expression = cast(Expression, branch.expression)
            cond = self.expression_temp(branch.expression)
            self.emit("ifFalse", arg1=cond, result=next_test_label)
            self.block(branch.block)
            self.emit("goto", result=exit_label)

        if stmt.else_statement is not None:
            if next_test_label is not None:
                self.emit("label", result=next_test_label)
            self.block(stmt.else_statement.block)
        else:
            if next_test_label is not None:
                self.emit("label", result=next_test_label)

        self.emit("label", result=exit_label)

    def get_label(self) -> str:
        self.label_count += 1
        return f"L{self.label_count}"

    def assignment_stmt(self, stmt: AssignmentStatement) -> None:
        value = self.expr_value(stmt.expression)
        self.emit(":=", arg1=value, result=stmt.identifier.lexeme)
        self.defined_vars.add(stmt.identifier.lexeme)

    def expr_value(self, expr: Expression | UnaryExpression) -> str:
        if isinstance(expr, UnaryExpression):
            return self.unary_expr_value(expr)
        return self.expression_value(expr)

    def unary_expr_value(self, expr: UnaryExpression) -> str:
        operand = self.expr_value(expr.operand)
        tmp = self.get_temp()
        op = expr.operator.lexeme
        if expr.operator.type == TokenType.NOT:
            op = "!"
        self.emit(op, arg1=operand, result=tmp)
        return tmp

    def expression_value(self, expr: Expression) -> str:
        left = self.operand_value(expr.left_operand)
        if expr.right_operand is None or expr.operator is None:
            return left
        right = self.operand_value(expr.right_operand)
        tmp = self.get_temp()
        op = expr.operator.lexeme
        if expr.operator.type == TokenType.OR:
            op = "||"
        elif expr.operator.type == TokenType.AND:
            op = "&&"
        self.emit(op, arg1=left, arg2=right, result=tmp)
        return tmp

    def operand_value(self, operand: Token | Expression | UnaryExpression) -> str:
        if isinstance(operand, Token):
            if operand.type == TokenType.IDENTIFIER:
                if operand.lexeme not in self.defined_vars:
                    raise RuntimeError(
                        "Undefined variable",
                        self.source_code,
                        operand.position,
                    )
                return operand.lexeme
            return operand.lexeme
        return self.expr_value(operand)

    def expression_temp(self, expr: Expression | UnaryExpression) -> str:
        # Ensures we always get a temp for conditionals, even if the expr is a bare identifier.
        value = self.expr_value(expr)
        if value.startswith("t"):
            return value
        tmp = self.get_temp()
        self.emit(":=", arg1=value, result=tmp)
        return tmp

    def get_temp(self) -> str:
        self.temp_count += 1
        return f"t{self.temp_count}"

    def emit(
        self,
        op: str,
        result: str | None = None,
        arg1: str | None = None,
        arg2: str | None = None,
    ) -> None:
        self.quads.append(Quadruple(op=op, result=result, arg1=arg1, arg2=arg2))
