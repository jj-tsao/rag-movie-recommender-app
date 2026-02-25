import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import joblib
from rank_bm25 import BM25Okapi
from reelix_core.config import BM25_PATH as RUNTIME_BM25_DIR

from reelix_retrieval.bm25_tokenizer import tokenize_for_bm25


def fit_and_save_bm25(
    media_type: str,
    corpus: List[str],
    bm25_dir: str,
):
    """Fit BM25 on the given corpus and save model + vocabulary.

    The BM25 model (IDF / doc-length stats) is always rebuilt from the
    current corpus.  If a vocabulary already exists on disk, new terms
    are appended with stable indices so that previously-stored sparse
    vectors in Qdrant remain compatible.
    """
    # Tokenize and process the corpus
    tokenized_corpus = [tokenize_for_bm25(doc) for doc in corpus]

    # Fit BM25 model on current corpus
    model = BM25Okapi(tokenized_corpus)

    # Load existing vocabulary or start fresh
    os.makedirs(bm25_dir, exist_ok=True)
    vocab_path = bm25_dir / f"{media_type}_bm25_vocab.joblib"

    if os.path.exists(vocab_path):
        vocab = joblib.load(vocab_path)
        next_index = max(vocab.values()) + 1 if vocab else 0
        print(f"Loaded existing vocabulary with {len(vocab)} terms from {bm25_dir}")
    else:
        vocab = {}
        next_index = 0

    # Extend vocabulary with any new terms
    for tokens in tokenized_corpus:
        for token in tokens:
            if token not in vocab:
                vocab[token] = next_index
                next_index += 1

    # Save model and vocabulary
    joblib.dump(model, bm25_dir / f"{media_type}_bm25_model.joblib")
    joblib.dump(vocab, vocab_path)

    print(f"BM25 model and vocabulary ({len(vocab)} terms) saved to {bm25_dir}")
    return model, vocab


def create_bm25_sparse_vector(
        document: str, 
        vocabulary: Dict[str, int], 
        bm25: BM25Okapi
):       
    # Tokenize corpus and document
    tokenized_document = tokenize_for_bm25(document)
    
    # Handle empty document case
    if not tokenized_document:
        print (f"Failed to tokenize document:'{document[:60]}'")
        return {'indices': [], 'values': []}

    # Calculate term frequencies (tf)
    term_counts = Counter(tokenized_document)

    # Calculate BM25 scores for each term in the document
    indices = []
    values = []
    
    for term, tf in term_counts.items():
        if term in vocabulary:
            term_index = vocabulary[term]
            idf = bm25.idf.get(term, 0)
            doc_length = len(tokenized_document)
            avg_doc_length = bm25.avgdl
            k1, b = bm25.k1, bm25.b
            
            # Standard BM25 formula
            numerator = idf * tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_length / avg_doc_length)
            
            if denominator != 0:
                weight = numerator / denominator
                indices.append(term_index)
                values.append(float(weight))  # Ensure float type for DB compatibility
    
    # Ensure indices are sorted for DB efficiency
    if indices:
        # Sort by index
        sorted_pairs = sorted(zip(indices, values), key=lambda x: x[0])
        indices, values = zip(*sorted_pairs)
        indices, values = list(indices), list(values)
        # density = len(indices) / len(vocabulary)
        # print(f"🧪 Sparse Vector Density: {len(indices)} terms / {len(vocabulary)} = {density:.4f}")
    
    return {'indices': indices, 'values': values}


# ---------------------------------------------------------------------------
# Sync pipeline BM25 output → runtime assets
# ---------------------------------------------------------------------------

_BM25_SUFFIXES = ("model", "vocab")


def _validate_bm25_pair(model_path: Path, vocab_path: Path) -> None:
    """Load and sanity-check a BM25 model + vocab pair. Raises on failure."""
    model = joblib.load(model_path)
    vocab = joblib.load(vocab_path)

    if not isinstance(model, BM25Okapi):
        raise TypeError(f"Expected BM25Okapi, got {type(model)}")
    if not isinstance(vocab, dict) or len(vocab) == 0:
        raise ValueError(f"Vocab is empty or not a dict ({type(vocab)})")
    if max(vocab.values()) != len(vocab) - 1:
        raise ValueError("Non-contiguous vocab indices")


def sync_bm25_to_runtime(
    media_type: str,
    pipeline_dir: Path,
    runtime_dir: Path = RUNTIME_BM25_DIR,
    max_backups: int = 2,
) -> None:
    """Validate, back up, and atomically copy pipeline BM25 files to runtime assets.

    Steps:
      1. Validate the new pipeline files (load + sanity check).
      2. Back up existing runtime files with a timestamp.
      3. Atomic copy: write to .tmp then rename.
      4. Prune old backups beyond ``max_backups`` per file.
    """
    pipeline_dir = Path(pipeline_dir)
    runtime_dir = Path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # 1. Validate new files before touching anything
    src_model = pipeline_dir / f"{media_type}_bm25_model.joblib"
    src_vocab = pipeline_dir / f"{media_type}_bm25_vocab.joblib"
    _validate_bm25_pair(src_model, src_vocab)

    # 2. Back up existing runtime files
    backup_dir = runtime_dir / "backup"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for suffix in _BM25_SUFFIXES:
        dst = runtime_dir / f"{media_type}_bm25_{suffix}.joblib"
        if dst.exists():
            shutil.copy2(dst, backup_dir / f"{media_type}_bm25_{suffix}_{ts}.joblib")

    # 3. Atomic copy: tmp file → rename
    for suffix in _BM25_SUFFIXES:
        src = pipeline_dir / f"{media_type}_bm25_{suffix}.joblib"
        dst = runtime_dir / f"{media_type}_bm25_{suffix}.joblib"
        tmp = dst.with_suffix(".joblib.tmp")
        shutil.copy2(src, tmp)
        tmp.rename(dst)

    # 4. Prune old backups (keep only max_backups most recent per file)
    for suffix in _BM25_SUFFIXES:
        pattern = f"{media_type}_bm25_{suffix}_*.joblib"
        backups = sorted(backup_dir.glob(pattern))
        for old in backups[:-max_backups]:
            old.unlink()
            print(f"  Pruned old backup: {old.name}")

    print(f"BM25 {media_type} files synced to runtime: {runtime_dir}")