"""Every example in the docstrings runs and prints what it shows (network examples are marked +SKIP)."""
import doctest
import importlib
import pkgutil

import pandas as pd
import pytest

import medcalc_kit as mk

MODULES = sorted(m.name for m in pkgutil.walk_packages(mk.__path__, "medcalc_kit.")
                 if m.name != "medcalc_kit.generation.hf")


@pytest.mark.parametrize("name", MODULES)
def test_docstring_examples(name):
    module = importlib.import_module(name)
    shortcuts = {n: getattr(mk, n) for n in mk.__all__ if not n.startswith("_")}
    globs = {"mk": mk, "pd": pd, **{n: v for n, v in shortcuts.items() if n not in vars(module)}}
    with pd.option_context("display.width", 120, "display.max_columns", 20):
        result = doctest.testmod(module, extraglobs=globs, optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE,
                                 verbose=False)
    assert result.failed == 0


def test_api_reference_is_up_to_date():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "docs" / "build_docs.py"
    spec = importlib.util.spec_from_file_location("build_docs", path)
    build_docs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_docs)
    assert (path.parent / "api.md").read_text() == build_docs.build_api(), "run: python docs/build_docs.py --api-only"
