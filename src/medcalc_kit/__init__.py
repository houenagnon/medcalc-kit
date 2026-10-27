"""medcalc-kit: data, executable calculators and diagnostic probes for MedCalc-Bench.

The shortcuts below cover a whole evaluation; every module (`data`, `calculators`, `probes`, `generation`,
`evaluate`, `expr`, `units`, `parsing`) has more.

    >>> import medcalc_kit as mk
    >>> ds = mk.load(equation_only=True)                # MedCalc-Bench-Verified    # doctest: +SKIP
    >>> ds = mk.data.demo()                             # or 4 offline examples
    >>> round(mk.derive("6", ds[1].entities).answer, 2) # reference computation
    22.86
    >>> items = mk.ProbeSuite().build(ds)               # every probe for every example: one row per item
    >>> items.groupby("probe", sort=False).size().to_dict()
    {'E': 4, 'K': 4, 'S': 4, 'A': 4, 'E2E': 4}
    >>> mk.score(items.iloc[0], '{"sex": "Female"}')["error_type"]   # score one answer
    'missing'
"""
from medcalc_kit import benchmark, calculators, data, evaluate, expr, generation, judge, parsing, probes, units
from medcalc_kit.benchmark import EvaluationReport, evaluate_model
from medcalc_kit.calculators import derive
from medcalc_kit.data import load
from medcalc_kit.evaluate import score_records, summary
from medcalc_kit.generation import read_records, run_items
from medcalc_kit.probes import ProbeSuite, reference_answer, score

__version__ = "0.5.3"

__all__ = ["EvaluationReport", "ProbeSuite", "benchmark", "calculators", "data", "derive", "evaluate", "evaluate_model",
           "expr", "generation", "judge", "load", "parsing", "probes", "read_records", "reference_answer", "run_items",
           "score", "score_records", "summary", "units", "__version__"]
