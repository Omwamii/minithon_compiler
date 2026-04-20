from typing import Any, Sequence
import colorama
from minithon.common import CommonException
from minithon.lexer import Token, TokenType
from PrettyPrint import PrettyPrintTree
from collections import defaultdict


class SyntaxError(CommonException):
    def __init__(
        self, msg: str, source_code: str, position: int, print_token=True
    ) -> None:
        super().__init__(msg, source_code, position, print_token)


class Node:
    def __init__(self, value: Any, children: Sequence["NodeWrapper"] = []) -> None:
        self.value = value
        self.children = children

    # Purely for debugging purposes
    def dirty_tree_str(self) -> str:
        string = str(self.value)
        if self.children:
            space_count = len(string) // 2
            space = " " * space_count
            children_string = " | ".join(
                child.node.dirty_tree_str() for child in self.children
            )
            string += f"\n{space}|{space}\n{space}V{space}\n{children_string}"
        return string


class NodeWrapper:
    def __init__(self, children: Sequence["NodeWrapper"] = []) -> None:
        self.node = Node(self, children)


class Expression(NodeWrapper):
    def __init__(
        self,
        left_operand: "Token | Expression | UnaryExpression",
        operator: "Token | None" = None,
        right_operand: "Token | Expression | UnaryExpression | None" = None,
    ) -> None:
        self.left_operand = left_operand
        self.operator = operator
        self.right_operand = right_operand
        super().__init__()

    def __str__(self) -> str:
        left_operand = (
            self.left_operand.lexeme
            if isinstance(self.left_operand, Token)
            else str(self.left_operand)
        )
        right_operand: str | None = None
        if isinstance(self.right_operand, Token):
            right_operand = self.right_operand.lexeme
        elif isinstance(self.right_operand, (Expression, UnaryExpression)):
            right_operand = str(self.right_operand)
        operator = self.operator.lexeme if isinstance(self.operator, Token) else None
        string = (
            f"{left_operand} {operator} {right_operand}"
            if right_operand is not None and operator is not None
            else left_operand
        )
        return string


class UnaryExpression(NodeWrapper):
    def __init__(self, operator: Token, operand: "Expression | UnaryExpression") -> None:
        self.operator = operator
        self.operand = operand
        super().__init__([operand])

    def __str__(self) -> str:
        return f"{self.operator.lexeme} {self.operand}"


ExprType = Expression | UnaryExpression


class ControlFlowStmtBlock(NodeWrapper):
    def __init__(
        self, keyword: Token, expression: ExprType | None, block: "Block"
    ) -> None:
        self.keyword = keyword
        self.expression = expression
        self.block = block
        super().__init__([block])

    def __str__(self) -> str:
        statement_string = (
            f"{self.keyword.lexeme} {self.expression}:"
            if self.expression is not None
            else f"{self.keyword.lexeme}:"
        )
        block_string = str(self.block)
        spaces_count = (len(statement_string) - len(block_string)) // 2
        string = f"{statement_string}\n{' '*spaces_count}{block_string}"
        return string


class IfStatementBlock(NodeWrapper):
    def __init__(
        self,
        if_statement: ControlFlowStmtBlock,
        elifs: list[ControlFlowStmtBlock],
        else_statement: ControlFlowStmtBlock | None,
    ) -> None:
        self.if_statement = if_statement
        self.elif_statements = elifs
        self.else_statement = else_statement
        children = [if_statement, *elifs]
        if else_statement is not None:
            children.append(else_statement)
        super().__init__(children)

    def __str__(self) -> str:
        return "IF_STMT_BLOCK"


class GenericStatement(NodeWrapper):
    def __init__(self, token: Token, string: str) -> None:
        self.token = token
        self.string = string
        super().__init__()

    def __str__(self) -> str:
        return self.string


class AssignmentStatement(NodeWrapper):
    def __init__(
        self,
        identifier_token: Token,
        expression: ExprType,
    ) -> None:
        self.identifier = identifier_token
        identifier_expression = Expression(identifier_token)
        self.expression = expression
        super().__init__([identifier_expression, expression])

    def __str__(self) -> str:
        return "ASSIGN_STMT"


class Block(NodeWrapper):
    def __init__(
        self,
        statements: list["StatementType"],
        id_: int,
        indent: int,
    ) -> None:
        self.statements = statements
        self.id = id_
        self.indent = indent
        super().__init__(statements)

    def __str__(self) -> str:
        return f"BLOCK #{self.id}"


class Program(NodeWrapper):
    def __init__(self, block: Block | None) -> None:
        self.block = block
        super().__init__([block] if block is not None else [])

    def __str__(self) -> str:
        return "PROGRAM"

    def print_parse_tree(self, pretty=True) -> None:
        if not pretty:
            print(self.node.dirty_tree_str())
            return

        def get_children(node_wrapper: NodeWrapper):
            return node_wrapper.node.children

        def get_value(node_wrapper: NodeWrapper):
            return str(node_wrapper.node.value)

        pt = PrettyPrintTree(get_children, get_value, color=colorama.Back.BLUE)  # type: ignore
        pt(self)  # type: ignore

    def print_parse_table(self) -> None:
        print_parse_table()


StatementType = (
    AssignmentStatement | GenericStatement | IfStatementBlock | ControlFlowStmtBlock
)


NON_TERMINALS = {
    "P", "SL", "SL_TAIL", "S", "SIMPLE", "COMPOUND", "AS",
    "B", "IS", "IS'", "WS", "E", "OrExpr", "OrExpr'",
    "AndExpr", "AndExpr'", "NotExpr", "CompExpr", "CompExpr'",
    "AE", "AE'", "T", "T'", "F"
}

TERMINALS = {
    "IDENTIFIER", "INTEGER", "FLOAT", "STRING", "LPAREN", "RPAREN",
    "NEWLINE", "INDENT", "DEDENT", "EOF",
    "IF", "ELIF", "ELSE", "WHILE", "PASS", "BREAK", "CONTINUE",
    "BOOL_TRUE", "BOOL_FALSE",
    "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "MODULUS",
    "EQUAL", "NOT_EQUAL", "LESS_THAN", "GREATER_THAN", "LESS_THAN_OR_EQUAL", "GREATER_THAN_OR_EQUAL",
    "ASSIGN", "COLON", "OR", "AND", "NOT"
}

EPSILON = "epsilon"

GRAMMAR = {
    "P": [["SL", "EOF"]],
    "SL": [["S", "SL_TAIL"]],
    "SL_TAIL": [["S", "SL_TAIL"], [EPSILON]],
    "S": [["SIMPLE", "NEWLINE"], ["COMPOUND"]],
    "SIMPLE": [["AS"], ["PASS"], ["BREAK"], ["CONTINUE"]],
    "COMPOUND": [["IS"], ["WS"]],
    "AS": [["IDENTIFIER", "ASSIGN", "E"]],
    "B": [["NEWLINE", "INDENT", "SL", "DEDENT"]],
    "IS": [["IF", "E", "COLON", "B", "IS'"]],
    "IS'": [["ELIF", "E", "COLON", "B", "IS'"], ["ELSE", "COLON", "B"], [EPSILON]],
    "WS": [["WHILE", "E", "COLON", "B"]],
    "E": [["OrExpr"], ["STRING"]],
    "OrExpr": [["AndExpr", "OrExpr'"]],
    "OrExpr'": [["OR", "AndExpr", "OrExpr'"], [EPSILON]],
    "AndExpr": [["NotExpr", "AndExpr'"]],
    "AndExpr'": [["AND", "NotExpr", "AndExpr'"], [EPSILON]],
    "NotExpr": [["NOT", "NotExpr"], ["CompExpr"], ["BOOL_TRUE"], ["BOOL_FALSE"]],
    "CompExpr": [["AE", "CompExpr'"]],
    "CompExpr'": [["EQUAL", "AE", "CompExpr'"], ["NOT_EQUAL", "AE", "CompExpr'"],
                  ["LESS_THAN", "AE", "CompExpr'"], ["GREATER_THAN", "AE", "CompExpr'"],
                  ["LESS_THAN_OR_EQUAL", "AE", "CompExpr'"], ["GREATER_THAN_OR_EQUAL", "AE", "CompExpr'"],
                  [EPSILON]],
    "AE": [["T", "AE'"]],
    "AE'": [["ADD", "T", "AE'"], ["SUBTRACT", "T", "AE'"], [EPSILON]],
    "T": [["F", "T'"]],
    "T'": [["MULTIPLY", "F", "T'"], ["DIVIDE", "F", "T'"], ["MODULUS", "F", "T'"], [EPSILON]],
    "F": [["IDENTIFIER"], ["INTEGER"], ["FLOAT"], ["LPAREN", "E", "RPAREN"]]
}

FIRST = defaultdict(set)
FOLLOW = defaultdict(set)


def compute_first(symbol: str) -> set:
    if symbol in FIRST:
        return FIRST[symbol]
    
    if symbol in TERMINALS or symbol == EPSILON:
        FIRST[symbol] = {symbol}
        return FIRST[symbol]
    
    if symbol in NON_TERMINALS:
        first_set = set()
        for production in GRAMMAR[symbol]:
            if production[0] == EPSILON:
                first_set.add(EPSILON)
            elif production[0] in TERMINALS:
                first_set.add(production[0])
            else:
                for sym in production:
                    sym_first = compute_first(sym)
                    first_set.update(sym_first - {EPSILON})
                    if EPSILON not in sym_first:
                        break
                    if sym == production[-1]:
                        first_set.add(EPSILON)
        FIRST[symbol] = first_set
        return first_set
    
    return set()


def compute_follow() -> None:
    FOLLOW["P"].add("EOF")
    
    for _ in range(len(NON_TERMINALS)):
        for non_terminal in NON_TERMINALS:
            for production in GRAMMAR[non_terminal]:
                for i, symbol in enumerate(production):
                    if symbol in NON_TERMINALS:
                        follow_set = set()
                        if i + 1 < len(production):
                            next_symbol = production[i + 1]
                            next_first = compute_first(next_symbol)
                            follow_set.update(next_first - {EPSILON})
                            if EPSILON in next_first or i + 1 == len(production):
                                follow_set.update(FOLLOW[non_terminal])
                        else:
                            follow_set.update(FOLLOW[non_terminal])
                        FOLLOW[symbol].update(follow_set)


def build_parse_table() -> dict:
    parse_table = defaultdict(dict)
    
    for non_terminal in NON_TERMINALS:
        for production in GRAMMAR[non_terminal]:
            first_set = set()
            for symbol in production:
                symbol_first = compute_first(symbol)
                first_set.update(symbol_first - {EPSILON})
                if EPSILON not in symbol_first:
                    break
                if symbol == production[-1]:
                    first_set.add(EPSILON)
            
            for terminal in first_set:
                if terminal != EPSILON:
                    key = (non_terminal, terminal)
                    parse_table[key] = production
            
            if EPSILON in first_set:
                for terminal in FOLLOW[non_terminal]:
                    key = (non_terminal, terminal)
                    if key not in parse_table:
                        parse_table[key] = production
    
    return parse_table


def print_parse_table() -> None:
    compute_follow()
    parse_table = build_parse_table()
    
    terminals_sorted = sorted(TERMINALS)
    terminals_filtered = [t for t in terminals_sorted if t != "EOF"] + ["EOF"]
    
    header = ["NT"] + terminals_filtered
    col_widths = [len(h) for h in header]
    
    table_data = []
    for nt in sorted(NON_TERMINALS):
        row = [nt]
        for term in terminals_filtered:
            prod = parse_table.get((nt, term))
            if prod:
                prod_str = " ".join(prod) if prod != [EPSILON] else "epsilon"
            else:
                prod_str = ""
            row.append(prod_str)
            col_widths[len(row) - 1] = max(col_widths[len(row) - 1], len(prod_str))
        table_data.append(row)
    
    for i, w in enumerate(col_widths):
        col_widths[i] = max(w, 3)
    
    def fmt(row):
        return " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))
    
    print(fmt(header))
    print("-+-".join("-" * w for w in col_widths))
    for row in table_data:
        print(fmt(row))
