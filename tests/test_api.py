"""The public API stays importable without torch / transformers, and every probe has the same interface."""
import subprocess
import sys

import medcalc_kit as mk


def test_top_level_namespaces():
    for name in ["calculators", "data", "evaluate", "expr", "generation", "parsing", "probes", "units"]:
        assert hasattr(mk, name)
    assert len(mk.calculators.list_calculators()) == 33


def test_probe_interface():
    assert list(mk.probes.PROBES) == ["E", "K", "S", "A", "E2E"]
    for name, p in mk.probes.PROBES.items():
        assert p.name == name and callable(p.build) and callable(p.score) and p.measures
        assert mk.probes.get(name) is p


def test_core_import_does_not_load_torch():
    code = "import sys, medcalc_kit; print('torch' in sys.modules or 'transformers' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
