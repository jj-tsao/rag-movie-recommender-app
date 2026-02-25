from __future__ import annotations

import re
import threading
from typing import List

from nltk.corpus import stopwords
from nltk.stem import PorterStemmer


_stop_words_lock = threading.Lock()

try:
    _STOP_WORDS = set(stopwords.words("english"))
except Exception as _e:
    print("Failed to preload NLTK stopwords:", _e)
    _STOP_WORDS = set()

_STEMMER = PorterStemmer()


def tokenize_for_bm25(text: str) -> List[str]:
    """
    Unified BM25 tokenizer shared between index-time and query-time.

    Uses regex tokenization (faster, deterministic, no NLTK Punkt dependency). Splits on non-alphanumeric boundaries, removes stopwords, applies Porter stemming.

    Used by both the data pipeline (index-time) and the query encoder (query-time) to ensure vocabulary consistency.
    """
    if not text or not isinstance(text, str):
        return []
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    with _stop_words_lock:
        sw = _STOP_WORDS
    filtered_tokens = [w for w in tokens if w not in sw]
    processed_tokens = [_STEMMER.stem(w) for w in filtered_tokens]
    return processed_tokens