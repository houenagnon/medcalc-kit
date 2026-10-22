"""Calculator definitions, one module per clinical family (importing registers them)."""
from medcalc_kit.calculators.equations import (  # noqa: F401 - registration order = benchmark listing order
    anthropometry,
    cardiovascular,
    dosage,
    electrolytes,
    metabolic,
    renal,
)
