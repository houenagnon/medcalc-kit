"""Safe arithmetic expression parser and evaluator.

LLM outputs are never passed to eval()/sympy.parse_expr (which uses eval). This module
implements a small recursive-descent parser over a whitelisted grammar:

    expr   := term (('+' | '-') term)*
    term   := unary (('*' | '/') unary)*
    unary  := ('+' | '-') unary | power
    power  := atom (('^' | '**') unary)?          # right-associative, binds tighter than unary minus on its left
    atom   := NUMBER | NAME | NAME '(' expr (',' expr)* ')' | '(' expr ')'

Only the functions in FUNCTIONS are callable. Names are variables resolved from an environment.

    >>> from medcalc_kit import expr
    >>> expr.evaluate("weight / (height / 100)^2", {"weight": 70, "height": 175})
    22.857142857142858
    >>> expr.evaluate("__import__('os').system('ls')")      # never executed: not in the grammar
    Traceback (most recent call last):
    ...
    medcalc_kit.expr.ExprError: unexpected character "'" at position 11
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Union

MAX_EXPR_LENGTH = 2000
MAX_DEPTH = 100


class ExprError(ValueError):
    """Raised for any syntax or evaluation error."""


@dataclass(frozen=True)
class Num:
    """A numeric literal."""
    value: float


@dataclass(frozen=True)
class Var:
    """A variable, resolved from the environment."""
    name: str


@dataclass(frozen=True)
class UnaryOp:
    """Unary + or -."""
    op: str  # '-' or '+'
    operand: Node


@dataclass(frozen=True)
class BinOp:
    """Binary operation: + - * / ^."""
    op: str  # '+', '-', '*', '/', '^'
    left: Node
    right: Node


@dataclass(frozen=True)
class Call:
    """Call of a whitelisted function (see FUNCTIONS)."""
    func: str
    args: tuple[Node, ...]


Node = Union[Num, Var, UnaryOp, BinOp, Call]

FUNCTIONS: dict[str, tuple[Callable[..., float], int | None]] = {
    # name: (implementation, arity or None for variadic >= 1)
    "sqrt": (math.sqrt, 1),
    "ln": (math.log, 1),
    "log": (math.log, 1),  # natural log, as in most clinical formula write-ups
    "log10": (math.log10, 1),
    "exp": (math.exp, 1),
    "abs": (abs, 1),
    "min": (min, None),
    "max": (max, None),
    # Python round (half-to-even), kept to mirror the reference implementations.
    "round": (lambda x, n=0: round(x, int(n)), None),
}

_UNICODE_MAP = str.maketrans({
    "×": "*", "·": "*", "⋅": "*", "÷": "/", "−": "-", "–": "-", "—": "-",
    "²": "^2", "³": "^3",
})

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<op>\*\*|[-+*/^(),])"
    r")"
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    if len(text) > MAX_EXPR_LENGTH:
        raise ExprError(f"expression longer than {MAX_EXPR_LENGTH} characters")
    text = text.translate(_UNICODE_MAP)
    tokens: list[tuple[str, str]] = []
    pos = 0
    text = text.rstrip()
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ExprError(f"unexpected character {text[pos]!r} at position {pos}")
        kind = m.lastgroup
        assert kind is not None
        tokens.append((kind, m.group(kind)))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.i = 0
        self.depth = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, value: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ExprError("unexpected end of expression")
        if value is not None and tok[1] != value:
            raise ExprError(f"expected {value!r}, got {tok[1]!r}")
        self.i += 1
        return tok

    def _enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ExprError("expression nested too deeply")

    def parse(self) -> Node:
        node = self.expr()
        if self.peek() is not None:
            raise ExprError(f"unexpected token {self.peek()[1]!r}")
        return node

    def expr(self) -> Node:
        node = self.term()
        while (tok := self.peek()) and tok[1] in "+-" and tok[0] == "op":
            self.take()
            node = BinOp(tok[1], node, self.term())
        return node

    def term(self) -> Node:
        node = self.unary()
        while (tok := self.peek()) and tok[0] == "op" and tok[1] in ("*", "/"):
            self.take()
            node = BinOp(tok[1], node, self.unary())
        return node

    def unary(self) -> Node:
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in ("+", "-"):
            self.take()
            self._enter()
            node = UnaryOp(tok[1], self.unary())
            self.depth -= 1
            return node
        return self.power()

    def power(self) -> Node:
        base = self.atom()
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in ("^", "**"):
            self.take()
            self._enter()
            node = BinOp("^", base, self.unary())
            self.depth -= 1
            return node
        return base

    def atom(self) -> Node:
        kind, value = self.take()
        if kind == "num":
            return Num(float(value))
        if kind == "name":
            nxt = self.peek()
            if nxt and nxt[1] == "(":
                if value not in FUNCTIONS:
                    raise ExprError(f"unknown function {value!r}")
                self.take("(")
                self._enter()
                args = [self.expr()]
                while self.peek() and self.peek()[1] == ",":
                    self.take(",")
                    args.append(self.expr())
                self.take(")")
                self.depth -= 1
                return Call(value, tuple(args))
            return Var(value)
        if value == "(":
            self._enter()
            node = self.expr()
            self.take(")")
            self.depth -= 1
            return node
        raise ExprError(f"unexpected token {value!r}")


def parse(text: str) -> Node:
    """Parse an expression string into an AST. Raises ExprError. `^` and `**` are powers; `×`, `÷`, `−` accepted.

    >>> parse("2 * x + 1")
    BinOp(op='+', left=BinOp(op='*', left=Num(value=2.0), right=Var(name='x')), right=Num(value=1.0))
    """
    return _Parser(_tokenize(text)).parse()


def evaluate(node: Node | str, env: Mapping[str, float] | None = None) -> float:
    """Evaluate an AST (or expression string) with variables from env. Raises ExprError.

    >>> evaluate("sqrt(x) + max(1, 2, 3)", {"x": 16})
    7.0
    >>> evaluate("1 / x", {"x": 0})
    Traceback (most recent call last):
    ...
    medcalc_kit.expr.ExprError: evaluation error: float division by zero
    """
    if isinstance(node, str):
        node = parse(node)
    env = env or {}
    try:
        return float(_eval(node, env))
    except ExprError:
        raise
    except (ArithmeticError, ValueError, TypeError) as exc:  # division by zero, log of negative, overflow...
        raise ExprError(f"evaluation error: {exc}") from exc


def _eval(node: Node, env: Mapping[str, float]) -> float:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Var):
        if node.name not in env:
            raise ExprError(f"unknown variable {node.name!r}")
        return float(env[node.name])
    if isinstance(node, UnaryOp):
        v = _eval(node.operand, env)
        return -v if node.op == "-" else v
    if isinstance(node, BinOp):
        a, b = _eval(node.left, env), _eval(node.right, env)
        if node.op == "+":
            return a + b
        if node.op == "-":
            return a - b
        if node.op == "*":
            return a * b
        if node.op == "/":
            return a / b
        result = a ** b
        if isinstance(result, complex):
            raise ExprError("complex result")
        return result
    if isinstance(node, Call):
        fn, arity = FUNCTIONS[node.func]
        if arity is not None and len(node.args) != arity:
            raise ExprError(f"{node.func} expects {arity} argument(s)")
        return fn(*(_eval(a, env) for a in node.args))
    raise ExprError(f"unknown node {node!r}")


def variables(node: Node | str) -> set[str]:
    """Free variable names of an expression.

    >>> sorted(variables("(140 - age) * weight / (72 * scr)"))
    ['age', 'scr', 'weight']
    """
    if isinstance(node, str):
        node = parse(node)
    if isinstance(node, Var):
        return {node.name}
    if isinstance(node, UnaryOp):
        return variables(node.operand)
    if isinstance(node, BinOp):
        return variables(node.left) | variables(node.right)
    if isinstance(node, Call):
        return set().union(*(variables(a) for a in node.args))
    return set()


def substitute(node: Node | str, env: Mapping[str, float]) -> Node:
    """Replace variables present in env by numeric literals (other variables are kept).

    >>> to_str(substitute("a * x + b", {"a": 2, "b": 3}))
    '2 * x + 3'
    """
    if isinstance(node, str):
        node = parse(node)
    if isinstance(node, Var) and node.name in env:
        return Num(float(env[node.name]))
    if isinstance(node, UnaryOp):
        return UnaryOp(node.op, substitute(node.operand, env))
    if isinstance(node, BinOp):
        return BinOp(node.op, substitute(node.left, env), substitute(node.right, env))
    if isinstance(node, Call):
        return Call(node.func, tuple(substitute(a, env) for a in node.args))
    return node


def replace_vars(node: Node | str, mapping: Mapping[str, Node]) -> Node:
    """Replace variables by sub-expressions (used to inline multi-step derivations).

    >>> to_str(replace_vars("bmi * 2", {"bmi": parse("w / h^2")}))
    'w / h^2 * 2'
    """
    if isinstance(node, str):
        node = parse(node)
    if isinstance(node, Var) and node.name in mapping:
        return mapping[node.name]
    if isinstance(node, UnaryOp):
        return UnaryOp(node.op, replace_vars(node.operand, mapping))
    if isinstance(node, BinOp):
        return BinOp(node.op, replace_vars(node.left, mapping), replace_vars(node.right, mapping))
    if isinstance(node, Call):
        return Call(node.func, tuple(replace_vars(a, mapping) for a in node.args))
    return node


def literals(node: Node) -> list[float]:
    """Numeric literals in left-to-right order.

    >>> literals(parse("140 - (104 + 24)"))
    [140.0, 104.0, 24.0]
    """
    if isinstance(node, Num):
        return [node.value]
    if isinstance(node, UnaryOp):
        return literals(node.operand)
    if isinstance(node, BinOp):
        return literals(node.left) + literals(node.right)
    if isinstance(node, Call):
        return [v for a in node.args for v in literals(a)]
    return []


def map_literals(node: Node, fn: Callable[[int, float], Node]) -> Node:
    """Rebuild the tree replacing the i-th literal (left-to-right) by fn(i, value).

    >>> to_str(map_literals(parse("140 - (104 + 24)"), lambda i, v: Var(["na", "cl", "hco3"][i])))
    'na - (cl + hco3)'
    """
    counter = iter(range(10**9))

    def rec(n: Node) -> Node:
        if isinstance(n, Num):
            return fn(next(counter), n.value)
        if isinstance(n, UnaryOp):
            return UnaryOp(n.op, rec(n.operand))
        if isinstance(n, BinOp):
            left = rec(n.left)
            return BinOp(n.op, left, rec(n.right))
        if isinstance(n, Call):
            return Call(n.func, tuple(rec(a) for a in n.args))
        return n

    return rec(node)


# ---------------------------------------------------------------- canonical form

def canonical(node: Node | str, sig: int = 10) -> tuple:
    """Order-insensitive structural key: flattens +/- and * / chains, sorts commutative operands,
    folds unary minus on literals. Two expressions with equal keys are identical up to
    commutativity/associativity of + and *, and a - (b + c) == a - b - c style regrouping.

    >>> canonical("a - (b + c)") == canonical("a - c - b")
    True
    >>> canonical("a / b") == canonical("b / a")
    False
    """
    if isinstance(node, str):
        node = parse(node)

    def num(v: float) -> tuple:
        return ("n", float(f"{v:.{sig}g}"))

    def terms(n: Node, sign: int, out: list) -> None:
        if isinstance(n, BinOp) and n.op in "+-":
            terms(n.left, sign, out)
            terms(n.right, sign if n.op == "+" else -sign, out)
        elif isinstance(n, UnaryOp):
            terms(n.operand, sign if n.op == "+" else -sign, out)
        else:
            out.append((sign, n))

    def factors(n: Node, exp: int, out: list) -> None:
        if isinstance(n, BinOp) and n.op in "*/":
            factors(n.left, exp, out)
            factors(n.right, exp if n.op == "*" else -exp, out)
        else:
            out.append((exp, n))

    def rec(n: Node) -> tuple:
        if isinstance(n, Num):
            return num(n.value)
        if isinstance(n, Var):
            return ("v", n.name)
        if isinstance(n, Call):
            args = [rec(a) for a in n.args]
            if n.func in ("min", "max"):
                args.sort(key=repr)
            return ("call", n.func, tuple(args))
        if isinstance(n, UnaryOp) or (isinstance(n, BinOp) and n.op in "+-"):
            ts: list = []
            terms(n, 1, ts)
            keyed = []
            for s, t in ts:
                k = rec(t)
                if k[0] == "n":  # fold the sign into numeric literals
                    keyed.append((1, ("n", s * k[1])))
                else:
                    keyed.append((s, k))
            if len(keyed) == 1 and keyed[0][0] == 1:
                return keyed[0][1]
            return ("sum", tuple(sorted(keyed, key=repr)))
        if isinstance(n, BinOp) and n.op in "*/":
            fs: list = []
            factors(n, 1, fs)
            return ("prod", tuple(sorted(((e, rec(f)) for e, f in fs), key=repr)))
        assert isinstance(n, BinOp) and n.op == "^"
        return ("pow", rec(n.left), rec(n.right))

    return rec(node)


# ---------------------------------------------------------------- conditions

_CMP_RE = re.compile(r"(<=|>=|==|!=|<|>|=)")
_CMP = {
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b, "==": lambda a, b: a == b, "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}
OTHERWISE = {"otherwise", "else", "default"}
ALWAYS = {"", "always", "true", "none", "all", "any"}


def evaluate_condition(text: str | None, env: Mapping[str, float]) -> bool:
    """Evaluate 'a <= x < b and y > 3 or ...' (chained comparisons, and/or; no parentheses).

    Empty / 'always' conditions are true. 'otherwise' must be handled by the caller.

    >>> evaluate_condition("18.5 <= bmi < 25", {"bmi": 22})
    True
    >>> evaluate_condition("age > 65 or scr >= 1.5", {"age": 40, "scr": 1.2})
    False
    """
    if text is None:
        return True
    t = text.strip().replace("≤", "<=").replace("≥", ">=").replace("&&", " and ").replace("||", " or ")
    if t.lower() in ALWAYS:
        return True
    if len(t) > MAX_EXPR_LENGTH:
        raise ExprError("condition too long")
    for disjunct in re.split(r"\bor\b", t, flags=re.IGNORECASE):
        ok = True
        for conj in re.split(r"\band\b", disjunct, flags=re.IGNORECASE):
            parts = _CMP_RE.split(conj)
            if len(parts) < 3 or len(parts) % 2 == 0:
                raise ExprError(f"cannot parse condition {conj!r}")
            values = [evaluate(p, env) for p in parts[0::2]]
            ops = parts[1::2]
            if not all(_CMP[op](values[i], values[i + 1]) for i, op in enumerate(ops)):
                ok = False
                break
        if ok:
            return True
    return False


_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 4}


def to_str(node: Node) -> str:
    """Render an AST back to a canonical string with minimal parentheses.

    >>> to_str(parse("((a + b)) * (c)"))
    '(a + b) * c'
    """
    return _to_str(node, 0)


def _fmt_num(v: float) -> str:
    return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)


def _to_str(node: Node, parent_prec: int, right_side: bool = False) -> str:
    if isinstance(node, Num):
        s = _fmt_num(node.value)
        return f"({s})" if node.value < 0 else s
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Call):
        return f"{node.func}({', '.join(_to_str(a, 0) for a in node.args)})"
    if isinstance(node, UnaryOp):
        s = f"{node.op}{_to_str(node.operand, 3)}"
        return f"({s})" if parent_prec >= 3 else s
    prec = _PREC[node.op]
    if node.op == "^":
        s = f"{_to_str(node.left, prec + 1)}^{_to_str(node.right, prec)}"
    else:
        s = f"{_to_str(node.left, prec)} {node.op} {_to_str(node.right, prec, right_side=True)}"
    needs = prec < parent_prec or (prec == parent_prec and right_side and node.op in "-/+*")
    return f"({s})" if needs else s
