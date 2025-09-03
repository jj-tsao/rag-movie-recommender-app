from typing import Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str,
        max_length: int = 512,
        batch_size: int = 32,
        device: str | None = "cuda" if torch.cuda.is_available() else "cpu",
        normalize: Optional[str] = None,
    ):
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name, trust_remote_code=True
        )
        # Enforce regression head for the reranker uses pairwise ranking with 1 logit
        if getattr(self.model.config, "num_labels", None) != 1:
            self.model.config.num_labels = 1
        self.device = device
        # Prefer FP16 on CUDA for faster matmul
        if isinstance(self.device, str) and self.device.startswith("cuda"):
            try:
                self.model.to(self.device, dtype=torch.float16)
                torch.set_float32_matmul_precision("high")
            except Exception:
                self.model.to(self.device)
        else:
            self.model.to(self.device)
        self.model.eval()
        self.max_length = max_length
        self.batch_size = batch_size
        self.normalize = normalize  # None | "minmax" | "zscore"

    @torch.inference_mode()
    def score(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        out_logits: list[float] = []
        for i in range(0, len(docs), self.batch_size):
            batch_docs = docs[i : i + self.batch_size]
            enc = self.tokenizer(
                [query] * len(batch_docs),
                batch_docs,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            enc = {k: v.to(self.device) for k, v in enc.items()}
            if isinstance(self.device, str) and self.device.startswith("cuda"):
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    logits = self.model(**enc).logits.squeeze(-1)
            else:
                logits = self.model(**enc).logits.squeeze(-1)
            out_logits.extend(logits.detach().float().cpu().tolist())
            scores = out_logits

        # Optional per-query normalization (for fusion/logging use)
        if self.normalize == "minmax":
            mn, mx = min(scores), max(scores)
            if mx != mn:
                scores = [(s - mn) / (mx - mn) for s in scores]
            else:
                scores = [0.5 for _ in scores]
        elif self.normalize == "zscore":
            import math

            mean = sum(scores) / len(scores)
            var = sum((s - mean) ** 2 for s in scores) / max(1, len(scores) - 1)
            std = math.sqrt(var) if var > 0 else 1.0
            scores = [(s - mean) / std for s in scores]

        return [float(s) for s in scores]
