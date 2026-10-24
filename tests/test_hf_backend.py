"""HFBackend.from_model wraps a model already in memory (no loading, no download)."""
from types import SimpleNamespace

import pytest

from medcalc_kit.generation.hf import HFBackend


class FakeModel:
    def __init__(self):
        self.config = SimpleNamespace(_name_or_path="org/tiny-model")
        self.generation_config = SimpleNamespace(eos_token_id=[2, 7])
        self.dtype = "torch.bfloat16"
        self.device = "cuda:1"
        self.evaluated = False

    def eval(self):
        self.evaluated = True
        return self


def fake_tokenizer():
    return SimpleNamespace(padding_side="right", pad_token=None, eos_token="</s>", eos_token_id=2)


def test_from_model_wraps_without_loading():
    model, tok = FakeModel(), fake_tokenizer()
    backend = HFBackend.from_model(model, tok, chat_template_kwargs={"enable_thinking": False})
    assert backend.model is model and backend.tokenizer is tok and model.evaluated
    assert backend.model_id == "org/tiny-model" and backend.device == "cuda:1" and backend.dtype == "bfloat16"
    assert tok.padding_side == "left" and tok.pad_token == "</s>" and backend.eos_ids == {2, 7}
    assert backend.chat_template_kwargs == {"enable_thinking": False}
    assert HFBackend.from_model(FakeModel(), fake_tokenizer(), model_id="pruned-50").model_id == "pruned-50"


@pytest.mark.gpu
def test_from_model_generates_with_a_real_model():
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    if not torch.cuda.is_available():
        pytest.skip("no GPU")
    name = "Qwen/Qwen2.5-3B-Instruct"
    lm = transformers.AutoModelForCausalLM.from_pretrained(name, dtype=torch.bfloat16, device_map="cuda:1")
    backend = HFBackend.from_model(lm, transformers.AutoTokenizer.from_pretrained(name), model_id="qwen-wrapped")
    text, n_in, n_out = backend.generate([{"role": "user", "content": "Reply with the number 4 only."}], 8)
    assert "4" in text and n_in > 0 and 0 < n_out <= 8
