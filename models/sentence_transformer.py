from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
import logging
import contextlib
import os, sys


def embedding_name():
    return "hf:sentence-transformers/all-MiniLM-L6-v2"


def embedding_desc():
    return (
        "General-purpose English sentence embedding model "
        "based on MiniLM. Optimized for semantic similarity, "
        "clustering, and retrieval tasks. Produces 384-dimensional "
        "float vectors. Not multilingual."
    )


_MODEL_CACHE = {}
huggingface_path = None


@contextlib.contextmanager
def silence_everything():
    with open(os.devnull, "w") as fnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = fnull
        sys.stderr = fnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr



# Suppress huggingface_hub logger
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

with silence_everything():
    huggingface_path = snapshot_download("sentence-transformers/all-MiniLM-L6-v2")

m = _MODEL_CACHE.get(huggingface_path)
if m is None:
    m = SentenceTransformer(huggingface_path)   # loads once per process
    _MODEL_CACHE[huggingface_path] = m



def embedding_dim():
    model = _MODEL_CACHE[huggingface_path]
    return model.get_sentence_embedding_dimension()



def embedding_encode(batch_index, batch, verbose = False) -> list[list[float]]:
    texts = [row_text for _, row_text in batch]
    row_ids = [row_id for row_id, _ in batch]
    model = _MODEL_CACHE.get(huggingface_path)

    if verbose:
        for i, (row_id, row_text) in enumerate(zip(row_ids, texts), 1):
            input_column_text = row_text[:40].replace('\n', '').replace('\r', '')
            print(f"[INFO] (batch {batch_index}, {i}/{len(batch)}) Updating vector for row id {row_id}: '{input_column_text}'")

    embeddings = model.encode(texts, batch_size=128, show_progress_bar=False)

    values = [(row_id, embedding.tolist()) for row_id, embedding in zip(row_ids, embeddings)]

    return values


