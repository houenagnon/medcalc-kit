from medcalc_kit.generation.artifacts import classify_generation, is_degenerate, repeated_ngram_share

GOOD = 'The creatinine clearance is computed with Cockcroft-Gault.\n{"result": 79.88}'


def test_order_of_categories():
    assert classify_generation("", 0, 100, False) == "empty"
    assert classify_generation("   \n", 3, 100, False) == "empty"
    assert classify_generation(GOOD, 100, 100, True) == "truncated"        # hit the budget even if parsable
    assert classify_generation(GOOD, 20, 100, False) == "format_invalid"
    assert classify_generation(GOOD, 20, 100, True) == "well_formed"


def test_degenerate_repetition():
    loop = "Let me compute the value again. " * 30
    assert repeated_ngram_share(loop) > 0.8 and is_degenerate(loop)
    assert classify_generation(loop, 200, 1024, True) == "degenerate"
    lines = "\n".join(["Step: multiply 0.85 by the weight"] * 3)
    assert is_degenerate(lines)


def test_normal_reasoning_is_not_degenerate():
    text = ("First convert the height: 158 cm is 62.2 inches. The ideal body weight for a woman is "
            "45.5 + 2.3 * (62.2 - 60) = 50.6 kg. The BMI is 27.5, so we use the adjusted body weight: "
            "50.6 + 0.4 * (68.6 - 50.6) = 57.8 kg. Then CrCl = (140 - 51) * 57.8 * 0.85 / (72 * 0.76).\n"
            '{"answer": 79.9}')
    assert not is_degenerate(text)
    assert classify_generation(text, 120, 2048, True) == "well_formed"
