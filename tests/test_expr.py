import math

import pytest

from medcalc_kit.expr import ExprError, canonical, evaluate, evaluate_condition, parse, substitute, to_str, variables


@pytest.mark.parametrize("expr, expected", [
    ("1 + 2 * 3", 7),
    ("(1 + 2) * 3", 9),
    ("2 ^ 3 ^ 2", 512),          # right-associative
    ("2 ** 3", 8),
    ("-2 ^ 2", -4),              # unary minus binds looser than power
    ("(-2) ^ 2", 4),
    ("2 ^ -1", 0.5),
    ("10 / 4 / 5", 0.5),          # left-associative
    ("8 - 3 - 2", 3),
    ("sqrt(16) + ln(1) + log10(100)", 6),
    ("min(3, 1, 2) + max(1, 5)", 6),
    ("round(2.345, 2)", 2.35),
    ("1.5e2 + .5", 150.5),
    ("3 × 4 − 2 ÷ 1", 10),        # unicode operators from LLM outputs
    ("5²", 25),
])
def test_evaluate_constants(expr, expected):
    assert evaluate(expr) == pytest.approx(expected)


def test_variables_and_env():
    assert variables("((140 - age) * w * k) / (72 * scr)") == {"age", "w", "k", "scr"}
    assert evaluate("(140 - age) / scr", {"age": 40, "scr": 2}) == 50


@pytest.mark.parametrize("bad", [
    "__import__('os')",
    "().__class__",
    "a.b",
    "open('x')",
    "1 +",
    "(1 + 2",
    "1 2",
    "foo(1)",
    "lambda: 1",
    "x[0]",
    "1; 2",
])
def test_rejects_unsafe_or_malformed(bad):
    with pytest.raises(ExprError):
        evaluate(bad, {"a": 1, "x": 1})


@pytest.mark.parametrize("bad", ["1 / 0", "ln(-1)", "sqrt(-4)", "(-8) ^ (1/3)", "10 ^ 1000", "unknown + 1"])
def test_evaluation_errors_are_exprerror(bad):
    with pytest.raises(ExprError):
        evaluate(bad)


def test_length_and_depth_limits():
    with pytest.raises(ExprError):
        parse("1+" * 2000 + "1")
    with pytest.raises(ExprError):
        parse("(" * 500 + "1" + ")" * 500)


def test_substitute_and_roundtrip():
    node = substitute("((140 - age) * w) / (72 * scr)", {"age": 87, "w": 48.0, "scr": 1.4})
    s = to_str(node)
    assert variables(s) == set()
    assert evaluate(s) == pytest.approx((140 - 87) * 48 / (72 * 1.4))


@pytest.mark.parametrize("expr", ["a - (b - c)", "a / (b / c)", "a - b - c", "(a ^ b) ^ c", "a ^ b ^ c",
                                  "-a ^ 2", "(-a) ^ 2", "a * (b + c)", "-(a + b)"])
def test_to_str_preserves_semantics(expr):
    env = {"a": 2.0, "b": 3.0, "c": 1.5}
    assert evaluate(to_str(parse(expr)), env) == pytest.approx(evaluate(expr, env))
    assert math.isfinite(evaluate(expr, env))


@pytest.mark.parametrize("a, b, same", [
    ("a - (b + c)", "a - b - c", True),
    ("a * b / c", "b * a / c", True),
    ("-(a - b)", "b - a", True),
    ("a - b", "b - a", False),
    ("a / (b * c)", "a / b / c", True),
    ("a / b * c", "a / (b * c)", False),
    ("x ^ (-1.2)", "x ^ -1.2", True),
    ("min(a, b)", "min(b, a)", True),
])
def test_canonical(a, b, same):
    assert (canonical(a) == canonical(b)) is same


@pytest.mark.parametrize("cond, env, expected", [
    ("scr <= 0.9", {"scr": 0.9}, True),
    ("18.5 <= bmi <= 24.9", {"bmi": 25}, False),
    ("age >= 18 and age < 65", {"age": 40}, True),
    ("x < 1 or x > 3", {"x": 2}, False),
    ("x ≥ 2", {"x": 2}, True),
    ("always", {}, True),
])
def test_conditions(cond, env, expected):
    assert evaluate_condition(cond, env) is expected


def test_condition_rejects_garbage():
    with pytest.raises(ExprError):
        evaluate_condition("x is big", {"x": 1})
