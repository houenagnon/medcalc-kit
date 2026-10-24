"""Hugging Face transformers backend (optional dependency: pip install medcalc-kit[hf])."""
from __future__ import annotations

from typing import Any

from medcalc_kit.generation.runner import Messages, run_items


class HFBackend:
    """Loads a causal LM on one device and generates greedily with its chat template (left padding for
    batches). chat_template_kwargs: e.g. {"enable_thinking": False} for Qwen3. Needs `pip install medcalc-kit[hf]`.

    deterministic=True makes torch use deterministic algorithms: with greedy decoding and one prompt at a time
    (batch_size=1), the same prompt then always gives the same text on the same hardware and software. `revision` is
    the model's commit on the Hub (when known), to record exactly which model answered.

    >>> from medcalc_kit.generation.hf import HFBackend
    >>> model = HFBackend("Qwen/Qwen2.5-3B-Instruct", device="cuda:0")              # doctest: +SKIP
    >>> model.generate([{"role": "user", "content": "2 + 2 = ?"}], max_new_tokens=16)  # doctest: +SKIP
    ('2 + 2 = 4', 32, 8)
    >>> mk.run_items(items, "outputs.jsonl", model, batch_size=16)                  # doctest: +SKIP
    """

    def __init__(self, model_id: str, device: str = "cuda:0", dtype: str = "bfloat16",
                 chat_template_kwargs: dict[str, Any] | None = None, deterministic: bool = False):
        if deterministic:
            _make_deterministic()
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=getattr(torch, dtype), device_map=device)
        self._setup(model, tokenizer, model_id, device, dtype, chat_template_kwargs)
        self.deterministic = deterministic

    @classmethod
    def from_model(cls, model: Any, tokenizer: Any, *, chat_template_kwargs: dict[str, Any] | None = None,
                   model_id: str | None = None, deterministic: bool = False) -> HFBackend:
        """Wrap a model already loaded (or modified, e.g. pruned or quantized) without loading it again.
        model_id defaults to the model's name_or_path; the tokenizer is set to left padding.

        >>> from transformers import AutoModelForCausalLM, AutoTokenizer          # doctest: +SKIP
        >>> lm = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", device_map="cuda:0")  # doctest: +SKIP
        >>> prune(lm)                                                             # doctest: +SKIP
        >>> model = HFBackend.from_model(lm, AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct"),
        ...                              model_id="qwen2.5-3b-pruned")             # doctest: +SKIP
        >>> report = mk.evaluate_model(model)                                     # doctest: +SKIP
        """
        if deterministic:
            _make_deterministic()
        self = cls.__new__(cls)
        self.deterministic = deterministic
        name = model_id or getattr(getattr(model, "config", None), "_name_or_path", None) or type(model).__name__
        dtype = str(getattr(model, "dtype", "")).removeprefix("torch.")
        self._setup(model, tokenizer, name, str(getattr(model, "device", "")), dtype, chat_template_kwargs)
        return self

    def _setup(self, model: Any, tokenizer: Any, model_id: str, device: str, dtype: str,
               chat_template_kwargs: dict[str, Any] | None) -> None:
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.chat_template_kwargs = chat_template_kwargs or {}
        self.tokenizer = tokenizer
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = model
        self.model.eval()
        self.revision = _revision(model, model_id)
        eos = self.model.generation_config.eos_token_id
        self.eos_ids = set(eos if isinstance(eos, list) else [eos]) | {self.tokenizer.eos_token_id}

    def generate_batch(self, batch: list[Messages], max_new_tokens: int) -> list[tuple[str, int, int]]:
        """Greedy answers for several chats: [(text, n_prompt_tokens, n_new_tokens), ...]."""
        import torch

        texts = [self.tokenizer.apply_chat_template(m, add_generation_prompt=True, tokenize=False,
                                                    **self.chat_template_kwargs) for m in batch]
        # the chat template already contains the special tokens (e.g. Llama's <|begin_of_text|>)
        enc = self.tokenizer(texts, return_tensors="pt", padding=True, add_special_tokens=False)
        enc = {k: v.to(self.model.device) for k, v in enc.items()}
        width = enc["input_ids"].shape[1]
        with torch.inference_mode():
            out = self.model.generate(
                **enc, max_new_tokens=max_new_tokens, do_sample=False,
                temperature=None, top_p=None, top_k=None, pad_token_id=self.tokenizer.pad_token_id)
        results = []
        for i in range(len(batch)):
            new = out[i, width:].tolist()
            stop = next((j for j, t in enumerate(new) if t in self.eos_ids), None)
            n_out = len(new) if stop is None else stop
            n_in = int(enc["attention_mask"][i].sum())
            results.append((self.tokenizer.decode(new[:n_out], skip_special_tokens=True), n_in, n_out))
        return results

    def generate(self, messages: Messages, max_new_tokens: int) -> tuple[str, int, int]:
        """Greedy answer for one chat: (text, n_prompt_tokens, n_new_tokens)."""
        return self.generate_batch([messages], max_new_tokens)[0]

    def run_items(self, items, out_path, meta=None, on_record=None, batch_size: int = 1) -> int:
        """`generation.run_items` with this model; decoding settings are added to each record's meta."""
        meta = {"dtype": self.dtype, "decoding": "greedy", "chat_template_kwargs": self.chat_template_kwargs,
                **(meta or {})}
        return run_items(items, out_path, None, self.model_id, meta, on_record,
                         generate_batch=self.generate_batch, batch_size=batch_size)


def _revision(model: Any, model_id: str) -> str | None:
    """The model's commit on the Hub: from its config, else from the local Hugging Face cache (offline)."""
    config = getattr(model, "config", None)
    commit = getattr(config, "_commit_hash", None)
    if commit:
        return commit
    try:
        from huggingface_hub import try_to_load_from_cache

        path = try_to_load_from_cache(getattr(config, "_name_or_path", None) or model_id, "config.json")
    except Exception:  # noqa: BLE001 - a local or unknown model simply has no revision
        return None
    if isinstance(path, str) and "/snapshots/" in path:
        return path.split("/snapshots/")[1].split("/")[0]
    return None


def _make_deterministic() -> None:
    """Deterministic torch kernels (CUBLAS_WORKSPACE_CONFIG must be set before CUDA starts: done here if not yet)."""
    import os

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch

    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


# Former name, kept for scripts written against the study code.
ModelRunner = HFBackend
