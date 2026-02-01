from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
import logging
import contextlib
import os, sys


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





def get_model() -> SentenceTransformer:
    m = _MODEL_CACHE.get(huggingface_path)
    if m is None:
        m = SentenceTransformer(huggingface_path)   # loads once per process
        _MODEL_CACHE[huggingface_path] = m
    return m


def embedding_dim():
    SentenceTransformer(huggingface_path).get_sentence_embedding_dimension()


