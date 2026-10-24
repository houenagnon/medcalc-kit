"""With default settings, items (messages, references, budgets) and verdicts are those of version 0.4.0."""
import json

from regression import SNAPSHOT, snapshot


def test_default_items_and_verdicts_are_unchanged():
    frozen = json.loads(SNAPSHOT.read_text())
    now = json.loads(json.dumps(snapshot(), sort_keys=True, ensure_ascii=False))
    assert now.keys() == frozen.keys()
    for item_id, ref in frozen.items():
        assert now[item_id] == ref, item_id
