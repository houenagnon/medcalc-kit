"""Dynamic splits: filters, split_off, folds, assignments saved and reloaded, concatenation, custom examples."""
import pytest

import medcalc_kit as mk
from medcalc_kit.data import MedCalcDataset, concat, from_records


def train_test():
    """demo(5) with 3 patients per calculator in train and 2 in test; train patient 1 of calculator 6 copies a test
    note (a leak)."""
    ds = mk.data.demo(5, split="train")
    test_ids = [f"train:{c}:{i}" for c in ("2", "6", "39", "5") for i in (4, 5)]
    ds = ds.assign_split(test_ids, "test")
    df = ds.df.copy()
    leak = df.example_id == "train:6:1"
    df.loc[leak, "Patient Note"] = df.loc[df.example_id == "train:6:4", "Patient Note"].iloc[0].upper()
    return MedCalcDataset(df)


def test_filter_takes_lists_and_conditions():
    ds = train_test()
    assert len(ds.filter(split=["train", "test"])) == 20
    assert len(ds.filter(split="test", calculator=[2, 6])) == 4
    assert len(ds.filter(where=lambda df: df["Calculator ID"] == "39", split="train")) == 3
    assert len(ds.filter(note_type="Extracted")) == 0


def test_split_off_is_stratified_reproducible_and_leak_free():
    ds = train_test()
    a = ds.split_off("dev", n=2, seed=1)
    assert a.splits().examples.to_dict() == {"dev": 8, "test": 8, "train": 4}
    assert a.filter(split="dev").example_ids == ds.split_off("dev", n=2, seed=1).filter(split="dev").example_ids
    for seed in range(10):
        clean = ds.split_off("dev", n=3, seed=seed, exclude_leaks=True)
        assert "train:6:1" not in clean.filter(split="dev").example_ids          # the leaking note never moves
    with pytest.raises(ValueError):
        ds.split_off("dev", fraction=0.5, n=2)
    with pytest.raises(ValueError):
        ds.split_off("dev", fraction=0.5, from_split="nope")


def test_folds_partition_the_split():
    folds = train_test().folds(3)
    devs = [set(f.filter(split="dev").example_ids) for f in folds]
    assert sum(map(len, devs)) == 12 and len(set().union(*devs)) == 12
    assert all(len(f.filter(split="test")) == 8 for f in folds)


def test_split_assignments_round_trip(tmp_path):
    ds = train_test().split_off("dev", fraction=0.34)
    path = ds.save_splits(tmp_path / "splits.csv")
    again = mk.data.demo(5, split="train").with_splits(path)
    assert dict(zip(again.example_ids, again.df.split)) == dict(zip(ds.example_ids, ds.df.split))
    assert len(train_test().with_splits({"train:2:1": "x"}, drop_unassigned=True)) == 1
    with pytest.raises(KeyError):
        train_test().assign_split(["nope"], "x")


def test_custom_examples_and_concat():
    mine = from_records([
        {"Calculator ID": "13", "Patient Note": "LMP 09/17/2011, cycle 21 days.", "Question": "Due date?",
         "entities": {"cycle length": 21}, "Ground Truth Answer": "06/16/2012", "Category": "date"},
        {"Calculator ID": 6, "Relevant Entities": '{"weight": [80, "kg"], "height": [180, "cm"]}',
         "Ground Truth Answer": 24.69}], split="mine")
    assert mine.example_ids == ["mine:13:1", "mine:6:1"]
    assert mine[0].ground_truth == mine[0].lower == "06/16/2012" and mine[1].calculator_name == "Body Mass Index (BMI)"
    both = mk.data.demo() + mine
    assert both.splits().examples.to_dict() == {"demo": 4, "mine": 2}
    assert both["demo:2:1"].note_type == "Synthetic" and both["mine:6:1"].note == ""     # NaN cells read as empty
    items = mk.ProbeSuite().build(both)
    assert items[items.example_id == "mine:13:1"].probe.tolist() == ["E2E"]
    with pytest.raises(ValueError, match="duplicate"):
        concat(mine, mine)


def test_evaluate_model_on_a_custom_split(tmp_path):
    ds = train_test().split_off("dev", n=1)
    report = mk.evaluate_model(lambda m, n: '{"answer": 1}', tmp_path, dataset=ds, split="dev")
    assert report.general.loc["all", "n"] == 4
    assert set(report.items.example_id) == set(ds.filter(split="dev").example_ids)
    k = report.items[report.items.probe == "K"]
    assert k.reference.map(lambda r: r["point_entities"] is not None).all()            # K points from train
    both = mk.evaluate_model(lambda m, n: '{"answer": 1}', tmp_path / "b", dataset=ds, split=["dev", "test"],
                             steps=())
    assert both.general.loc["all", "n"] == 12
