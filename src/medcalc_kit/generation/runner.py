"""Greedy generation over probe items, with raw-output logging, resume, de-duplication and batching.

- Identical prompts (same messages and token budget) are generated ONCE and the output is copied to every
  item sharing the prompt (`prompt_key`). With greedy decoding they would be identical anyway; this matters
  for K, whose prompts repeat across examples of a calculator.
- Prompts are batched by token budget and length; one JSON record is appended per item.
- Resumable: items already in the output file are skipped; a failing batch is retried item by item.
- Items can be a DataFrame (probes.ProbeSuite.build) or a list of dicts; `read_records` loads the output file as a
  DataFrame, one row per record.

Any model can be used: an object with `generate_batch` (e.g. generation.hf.HFBackend) or `generate`, or a plain
function `generate(messages, max_new_tokens)` returning the text (or `(text, n_prompt_tokens, n_new_tokens)`).

    >>> def echo(messages, max_new_tokens):                     # a "model" that always answers 12
    ...     return '{"result": 12}'
    >>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
    >>> run_items(items, "outputs.jsonl", echo)                 # doctest: +SKIP
    4
    >>> read_records("outputs.jsonl")[["item_id", "text"]]      # doctest: +SKIP
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit.probes.common import as_items

Messages = list[dict[str, str]]
# generate(messages, max_new_tokens) -> (text, n_prompt_tokens, n_new_tokens)
GenerateFn = Callable[[Messages, int], tuple[str, int, int]]
# generate_batch(list of messages, max_new_tokens) -> list of (text, n_prompt_tokens, n_new_tokens)
GenerateBatchFn = Callable[[list[Messages], int], list[tuple[str, int, int]]]


def prompt_key(messages: Messages, max_new_tokens: int) -> str:
    """Short hash identifying a prompt (messages + token budget): items with the same key get the same answer.

    >>> prompt_key([{"role": "user", "content": "2 + 2 = ?"}], 64)
    '14ce2533d1765515'
    """
    payload = json.dumps([messages, max_new_tokens], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    recs = []
    with p.open() as f:
        for line in f:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:  # a line truncated by an interruption
                continue
    return recs


def read_records(path: str | Path) -> pd.DataFrame:
    """The generation records of an output file, one row per record; `meta` is flattened into `meta.<key>`
    columns. A line truncated by an interruption is skipped. Empty DataFrame if the file does not exist.

    Columns: item_id, example_id, calculator_id, probe, model_id, prompt_key, shared_generation, text,
    n_prompt_tokens, n_new_tokens, truncated, seconds, batch_size, error, timestamp, meta.<key>...

    >>> df = read_records("outputs.jsonl")                      # doctest: +SKIP
    >>> df[["item_id", "text", "n_new_tokens"]]                 # doctest: +SKIP
    """
    recs = _load_records(path)
    return pd.json_normalize(recs, max_level=1) if recs else pd.DataFrame()


def done_item_ids(out_path: str | Path) -> set[str]:
    """item_ids already present in an output file (successful generations only): what `run_items` skips.

    >>> done_item_ids("does-not-exist.jsonl")
    set()
    """
    return {rec["item_id"] for rec in _load_records(out_path) if rec.get("error") is None}


def _ensure_trailing_newline(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as fb:
            fb.seek(-1, 2)
            needs_newline = fb.read(1) != b"\n"   # last write was interrupted mid-line
        if needs_newline:
            with path.open("a") as f:
                f.write("\n")


def model_name(model: Any) -> str:
    """The id recorded for a model: its `model_id` attribute, else its (function) name.

    >>> def my_model(messages, max_new_tokens): ...
    >>> model_name(my_model)
    'my_model'
    """
    return getattr(model, "model_id", None) or getattr(model, "__name__", None) or type(model).__name__


def _as_triple(out: str | tuple[str, int, int]) -> tuple[str, int, int]:
    return (out, 0, 0) if isinstance(out, str) else tuple(out)


def run_items(
    items: pd.DataFrame | Iterable[dict[str, Any]],
    out_path: str | Path,
    model: Any = None,
    model_id: str | None = None,
    meta: dict[str, Any] | None = None,
    on_record: Callable[[dict[str, Any]], None] | None = None,
    generate_batch: GenerateBatchFn | None = None,
    batch_size: int = 1,
) -> int:
    """Generate an answer for every item not yet in `out_path` and append one JSON record per item (resumable:
    run it again after an interruption). Returns the number of records written.

    model:          an object with `generate_batch(list_of_messages, max_new_tokens)` (e.g. HFBackend) or
                    `generate(messages, max_new_tokens)`, or such a function. `generate` returns the text or
                    (text, n_prompt_tokens, n_new_tokens); without token counts, truncation cannot be detected.
    model_id:       recorded in each record (default: the backend's `model_id`, else the function's name).
    meta:           extra information stored in every record (decoding settings, seed...).
    on_record:      called with each record as it is written (progress bars, logging).
    generate_batch: a batch function, instead of `model`.
    batch_size:     prompts generated together (same token budget, similar lengths).

    >>> import tempfile, pathlib
    >>> out = pathlib.Path(tempfile.mkdtemp()) / "outputs.jsonl"
    >>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
    >>> def always_12(messages, max_new_tokens):
    ...     return '{"result": 12}'
    >>> run_items(items, out, always_12)
    4
    >>> run_items(items, out, always_12)                        # already done: nothing to generate
    0
    >>> records = read_records(out)                             # one row per item (in generation order)
    >>> len(records), records.loc[0, "model_id"], records.loc[0, "text"]
    (4, 'always_12', '{"result": 12}')
    """
    if generate_batch is None:
        if model is None:
            raise ValueError("pass a model (backend or generate function) or generate_batch")
        if hasattr(model, "generate_batch"):
            generate_batch = model.generate_batch
        else:
            generate = getattr(model, "generate", model)
            generate_batch = lambda msgs, n: [generate(m, n) for m in msgs]  # noqa: E731
    if model_id is None:
        model_id = model_name(model if model is not None else generate_batch)
    items = as_items(items)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_trailing_newline(out_path)
    skip = done_item_ids(out_path)

    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in items:
        if item["item_id"] not in skip:
            groups.setdefault(prompt_key(item["messages"], item["max_new_tokens"]), []).append(item)

    # batches share a token budget; within a budget, similar prompt lengths go together
    keys = sorted(groups, key=lambda k: (groups[k][0]["max_new_tokens"],
                                         sum(len(m["content"]) for m in groups[k][0]["messages"])))
    batches: list[list[str]] = []
    for k in keys:
        if batches and len(batches[-1]) < batch_size and \
                groups[batches[-1][0]][0]["max_new_tokens"] == groups[k][0]["max_new_tokens"]:
            batches[-1].append(k)
        else:
            batches.append([k])

    n = 0
    with out_path.open("a") as f:
        for batch in batches:
            heads = [groups[k][0] for k in batch]
            budget = heads[0]["max_new_tokens"]
            t0 = time.perf_counter()
            try:
                outputs: list[tuple[str, int, int] | Exception] = list(
                    generate_batch([h["messages"] for h in heads], budget))
            except Exception:  # noqa: BLE001 - retry one by one so a single bad prompt cannot sink a batch
                _free_cuda_memory()
                outputs = []
                for h in heads:
                    try:
                        outputs.append(generate_batch([h["messages"]], budget)[0])
                    except Exception as exc:  # noqa: BLE001 - recorded, the run continues
                        _free_cuda_memory()
                        outputs.append(exc)
            seconds = round((time.perf_counter() - t0) / len(batch), 3)
            for k, out in zip(batch, outputs):
                for j, item in enumerate(groups[k]):
                    if isinstance(out, Exception):
                        text, n_in, n_out, error = "", 0, 0, f"{type(out).__name__}: {out}"
                    else:
                        (text, n_in, n_out), error = _as_triple(out), None
                    rec = {
                        "item_id": item["item_id"],
                        "example_id": item["example_id"],
                        "calculator_id": item["calculator_id"],
                        "probe": item["probe"],
                        "model_id": model_id,
                        "prompt_key": k,
                        "shared_generation": j > 0,
                        "text": text,
                        "n_prompt_tokens": n_in,
                        "n_new_tokens": n_out,
                        "truncated": n_out >= item["max_new_tokens"],
                        "seconds": seconds if j == 0 else 0.0,
                        "batch_size": len(batch),
                        "error": error,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "meta": meta or {},
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
                    if on_record:
                        on_record(rec)
            f.flush()
    return n


def _free_cuda_memory() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
