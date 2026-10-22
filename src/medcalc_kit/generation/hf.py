"""Hugging Face transformers backend (optional dependency: pip install medcalc-kit[hf])."""
from __future__ import annotations

from typing import Any

from medcalc_kit.generation.runner import Messages, run_items


class HFBackend:
    """Loads a causal LM on one device and generates greedily with its chat template (left padding for
    batches). chat_template_kwargs: e.g. {"enable_thinking": False} for Qwen3. Needs `pip install medcalc-kit[hf]`.

    >>> from medcalc_kit.generation.hf import HFBackend
    >>> model = HFBackend("Qwen/Qwen2.5-3B-Instruct", device="cuda:0")              # doctest: +SKIP
    >>> model.generate([{"role": "user", "content": "2 + 2 = ?"}], max_new_tokens=16)  # doctest: +SKIP
    ('2 + 2 = 4', 32, 8)
    >>> mk.run_items(items, "outputs.jsonl", model, batch_size=16)                  # doctest: +SKIP
    """

    def __init__(self, model_id: str, device: str = "cuda:0", dtype: str = "bfloat16",
                 chat_template_kwargs: dict[str, Any] | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.chat_template_kwargs = chat_template_kwargs or {}
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, dtype=getattr(torch, dtype), device_map=device)
        self.model.eval()
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


# Former name, kept for scripts written against the study code.
ModelRunner = HFBackend
