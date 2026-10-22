"""Runner logic without GPU: JSONL records, resume, error capture, de-duplication, batching."""
import json

from medcalc_kit.generation.runner import done_item_ids, prompt_key, run_items


def make_items(n, probe="S", same_prompt=False):
    return [{"item_id": f"x:{i}:{probe}", "example_id": f"x:{i}", "calculator_id": "2", "probe": probe,
             "messages": [{"role": "user", "content": "same" if same_prompt else f"q{i}"}],
             "max_new_tokens": 8} for i in range(n)]


def fake_generate(messages, max_new_tokens):
    return f"answer to {messages[-1]['content']}", 3, 5


def read(out):
    return [json.loads(line) for line in out.open()]


def test_records_and_resume(tmp_path):
    out = tmp_path / "out.jsonl"
    assert run_items(make_items(3), out, fake_generate, "fake") == 3
    assert run_items(make_items(5), out, fake_generate, "fake") == 2      # only the 2 new items
    recs = read(out)
    assert sorted(r["item_id"] for r in recs) == [f"x:{i}:S" for i in range(5)]
    r0 = next(r for r in recs if r["item_id"] == "x:0:S")
    assert r0["text"] == "answer to q0" and r0["model_id"] == "fake" and r0["truncated"] is False


def test_persistent_error_is_recorded_and_retried_next_run(tmp_path):
    out = tmp_path / "out.jsonl"
    state = {"broken": True}

    def gen(messages, max_new_tokens):
        if state["broken"] and messages[-1]["content"] == "q0":
            raise RuntimeError("CUDA out of memory")
        return "ok", 1, 1

    run_items(make_items(2), out, gen, "fake")
    recs = {r["item_id"]: r for r in read(out)}
    assert recs["x:0:S"]["error"].startswith("RuntimeError") and recs["x:1:S"]["error"] is None
    assert done_item_ids(out) == {"x:1:S"}
    state["broken"] = False
    assert run_items(make_items(2), out, gen, "fake") == 1


def test_transient_batch_error_falls_back_to_single_items(tmp_path):
    out = tmp_path / "out.jsonl"
    calls = {"n": 0}

    def gen_batch(batch, n):
        calls["n"] += 1
        if len(batch) > 1:
            raise RuntimeError("OOM on the full batch")
        return [("ok", 1, 1)]

    run_items(make_items(3), out, None, "fake", generate_batch=gen_batch, batch_size=4)
    assert all(r["error"] is None for r in read(out)) and calls["n"] == 4   # 1 failed batch + 3 singles


def test_truncated_line_is_ignored(tmp_path):
    out = tmp_path / "out.jsonl"
    run_items(make_items(1), out, fake_generate, "fake")
    with out.open("a") as f:
        f.write('{"item_id": "x:1:S", "te')                                # interrupted write
    assert done_item_ids(out) == {"x:0:S"}
    assert run_items(make_items(2), out, fake_generate, "fake") == 1      # x:1 regenerated on a clean line
    assert done_item_ids(out) == {"x:0:S", "x:1:S"}


def test_identical_prompts_are_generated_once(tmp_path):
    out = tmp_path / "out.jsonl"
    calls = {"n": 0}

    def gen(messages, max_new_tokens):
        calls["n"] += 1
        return "shared", 1, 1

    assert run_items(make_items(4, probe="K", same_prompt=True), out, gen, "fake") == 4
    recs = read(out)
    assert calls["n"] == 1
    assert len({r["prompt_key"] for r in recs}) == 1
    assert [r["shared_generation"] for r in recs] == [False, True, True, True]
    assert all(r["text"] == "shared" for r in recs)


def test_batches_respect_size_and_token_budget(tmp_path):
    out = tmp_path / "out.jsonl"
    seen = []

    def gen_batch(batch, n):
        seen.append((len(batch), n))
        return [("ok", 1, 1)] * len(batch)

    items = make_items(5) + [dict(it, item_id=it["item_id"] + "b", max_new_tokens=16) for it in make_items(3)]
    run_items(items, out, None, "fake", generate_batch=gen_batch, batch_size=2)
    assert all(size <= 2 for size, _ in seen)
    assert sum(size for size, n in seen if n == 8) == 5 and sum(size for size, n in seen if n == 16) == 3


def test_prompt_key_depends_on_budget():
    m = [{"role": "user", "content": "x"}]
    assert prompt_key(m, 8) != prompt_key(m, 16) and prompt_key(m, 8) == prompt_key(list(m), 8)


def test_dataframe_items_and_read_records(tmp_path):
    import pandas as pd

    from medcalc_kit.generation import read_records

    out = tmp_path / "out.jsonl"
    assert run_items(pd.DataFrame(make_items(2)), out, fake_generate, "fake", meta={"seed": 1}) == 2
    with out.open("a") as f:
        f.write('{"item_id": "x:9:S", "te')                                # interrupted write
    df = read_records(out)
    assert df.item_id.tolist() == ["x:0:S", "x:1:S"] and (df["meta.seed"] == 1).all()
    assert read_records(tmp_path / "missing.jsonl").empty


def test_model_object_with_generate_method(tmp_path):
    class Model:
        model_id = "obj"

        def generate(self, messages, max_new_tokens):
            return "plain text"                                         # text only: token counts unknown

    out = tmp_path / "out.jsonl"
    assert run_items(make_items(2), out, Model()) == 2
    recs = read(out)
    assert {r["model_id"] for r in recs} == {"obj"} and recs[0]["text"] == "plain text"
