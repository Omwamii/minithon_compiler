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
    """ICG-time runtime error with source-location reporting."""

    def __init__(
        self, msg: str, source_code: str, position: int, print_token=True
    ) -> None:
        super().__init__(msg, source_code, position, print_token)


@dataclass(frozen=True, slots=True)
class Quadruple:
    """Quadruple IR instruction in the form: (op, result, arg1, arg2)."""

    op: str
    result: str | None = None
    arg1: str | None = None
    arg2: str | None = None


class ICG:
    def __init__(self) -> None:
        """Initialize ICG state used during quad generation."""
        self.quads: list[Quadruple] = []
        self.temp_count = 0
        self.label_count = 0
        self.loop_stack: list[tuple[str, str]] = []
        self.defined_vars: set[str] = set()
        self.source_code: str

    def generate(self, program: Program, source_code: str) -> str:
        """Generate formatted quadruple IR text for a parsed `Program`."""
        quads = self.generate_quads(program, source_code)
        return self.format_quads(quads)

    def generate_quads(self, program: Program, source_code: str) -> list[Quadruple]:
        """Lower a parsed `Program` into a list of quadruples."""
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
        """Format quadruples as numbered lines `(OP, RESULT, ARG1, ARG2)`."""
        lines: list[str] = []
        for index, q in enumerate(quads, start=1):
            res = "" if q.result is None else q.result
            a1 = "" if q.arg1 is None else q.arg1
            a2 = "" if q.arg2 is None else q.arg2
            lines.append(f"{index:d}: ({q.op}, {res}, {a1}, {a2})")
        return "\n".join(lines)

    def block(self, block: Block) -> None:
        """Generate quads for each statement in a block, in order."""
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
        """Handle simple statements (`break`/`continue`/`pass`) in a loop context."""
        if not self.loop_stack:
            return
        continue_label, break_label = self.loop_stack[-1]
        if stmt.token.type == TokenType.CONTINUE:
            self.emit("goto", result=continue_label)
        elif stmt.token.type == TokenType.BREAK:
            self.emit("goto", result=break_label)

    def while_stmt(self, stmt: ControlFlowStmtBlock) -> None:
        """Lower a `while` statement into labels, conditional branch, body, and back-edge."""
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
        """Lower an `if/elif/else` chain into conditional branches and join label.

        Also performs a simple definite-assignment merge: after the chain, only variables
        defined on all possible paths remain in `defined_vars`.
        """
        # Definite-assignment handling:
        # - Each branch body must be analyzed starting from the same pre-if set.
        # - After the if-chain, only variables defined on all possible paths are kept.
        pre_defined = set(self.defined_vars)

        exit_label = self.get_label()
        next_test_label: str | None = None

        branches: list[ControlFlowStmtBlock] = [
            stmt.if_statement,
            *stmt.elif_statements,
        ]
        branch_out_sets: list[set[str]] = []

        for branch in branches:
            if next_test_label is not None:
                self.emit("label", result=next_test_label)

            # Condition is evaluated with the pre-if definitions.
            self.defined_vars = set(pre_defined)

            next_test_label = self.get_label()
            branch.expression = cast(Expression, branch.expression)
            cond = self.expression_temp(branch.expression)
            self.emit("ifFalse", arg1=cond, result=next_test_label)

            # Body is also analyzed as if entered directly from pre-if.
            self.defined_vars = set(pre_defined)
            self.block(branch.block)
            branch_out_sets.append(set(self.defined_vars))
            self.emit("goto", result=exit_label)

        if stmt.else_statement is not None:
            if next_test_label is not None:
                self.emit("label", result=next_test_label)
            self.defined_vars = set(pre_defined)
            self.block(stmt.else_statement.block)
            branch_out_sets.append(set(self.defined_vars))
        else:
            # No else means there's a path where none of the branch bodies execute.
            if next_test_label is not None:
                self.emit("label", result=next_test_label)
            branch_out_sets.append(set(pre_defined))

        self.emit("label", result=exit_label)

        # Merge: keep only vars defined on all possible paths.
        must_defined = set.intersection(*branch_out_sets) if branch_out_sets else pre_defined
        self.defined_vars = must_defined

    def get_label(self) -> str:
        """Return a fresh label name (e.g. `L1`, `L2`, ...)."""
        self.label_count += 1
        return f"L{self.label_count}"

    def assignment_stmt(self, stmt: AssignmentStatement) -> None:
        """Lower an assignment statement by evaluating the RHS and emitting `:=`."""
        value = self.expr_value(stmt.expression)
        self.emit(":=", arg1=value, result=stmt.identifier.lexeme)
        self.defined_vars.add(stmt.identifier.lexeme)

    def expr_value(self, expr: Expression | UnaryExpression) -> str:
        """Compute a value for an expression, returning an identifier/literal or a temp name."""
        if isinstance(expr, UnaryExpression):
            return self.unary_expr_value(expr)
        return self.expression_value(expr)

    def unary_expr_value(self, expr: UnaryExpression) -> str:
        """Lower a unary expression (currently `not`) into a temp-producing quad."""
        operand = self.expr_value(expr.operand)
        tmp = self.get_temp()
        op = expr.operator.lexeme
        if expr.operator.type == TokenType.NOT:
            op = "!"
        self.emit(op, arg1=operand, result=tmp)
        return tmp

    def expression_value(self, expr: Expression) -> str:
        """Lower a binary expression into a temp-producing quad (e.g. `+`, `<`, `==`)."""
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
        """Convert an operand into a value string, raising on undefined identifiers."""
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
        """Ensure `expr` is represented by a temp name (useful for branch conditions)."""
        # Ensures we always get a temp for conditionals, even if the expr is a bare identifier.
        value = self.expr_value(expr)
        if value.startswith("t"):
            return value
        tmp = self.get_temp()
        self.emit(":=", arg1=value, result=tmp)
        return tmp

    def get_temp(self) -> str:
        """Return a fresh temporary name (e.g. `t1`, `t2`, ...)."""
        self.temp_count += 1
        return f"t{self.temp_count}"

    def emit(
        self,
        op: str,
        result: str | None = None,
        arg1: str | None = None,
        arg2: str | None = None,
    ) -> None:
        """Append one quadruple instruction to the output list."""
        self.quads.append(Quadruple(op=op, result=result, arg1=arg1, arg2=arg2))
