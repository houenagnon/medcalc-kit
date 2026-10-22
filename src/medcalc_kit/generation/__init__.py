"""Running models on probe items: backend-agnostic runner, generation-artifact classification, HF backend.

The Hugging Face backend needs the optional dependencies (pip install medcalc-kit[hf]):
    >>> from medcalc_kit.generation.hf import HFBackend
"""
from medcalc_kit.generation.artifacts import CATEGORIES, classify_generation, is_degenerate
from medcalc_kit.generation.runner import done_item_ids, prompt_key, read_records, run_items

__all__ = ["CATEGORIES", "classify_generation", "done_item_ids", "is_degenerate", "prompt_key", "read_records",
           "run_items"]
