from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
import logging
import contextlib
import os, sys
import textwrap, json
from typing import Iterable, List, Tuple, Any
from pathlib import Path
import yaml
import requests
from urllib.parse import urljoin
import inspect

exec_local = True

if not os.getenv("NUCLIO"):
    # Read the configuration
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config = None
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)

    model_settings = next(
        item[Path(__file__).stem] 
        for item in config['models'] 
        if isinstance(item, dict) and 'hf_st_all_minilm_l6' in item
    )

    if 'nuclio' in model_settings:
        exec_local = False

# enf if
#


if exec_local:
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

# end if
#


def embedding_label() -> str:
    if exec_local:
        return "Hugging Face Sentence Transformer all-MiniLM-L6-v2"

    if 'nuclio' in model_settings:
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        response = requests.get(url)
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_description() -> str:
    if exec_local:
        return textwrap.dedent(
            """
            General-purpose English sentence embedding model
            based on MiniLM. Optimized for semantic similarity,
            clustering, and retrieval tasks. Produces 384-dimensional
            float vectors. Not multilingual.
            https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
            """
        ).strip()

    if 'nuclio' in model_settings:
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        response = requests.get(url)
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_dim() -> int:
    if exec_local:
        model = _MODEL_CACHE[huggingface_path]
        return model.get_sentence_embedding_dimension()

    if 'nuclio' in model_settings:
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        response = requests.get(url)
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_index_opclass() -> str:
    if exec_local:
        return "vector_cosine_ops"

    if 'nuclio' in model_settings:
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        response = requests.get(url)
        response.raise_for_status()  # raises on non-200
        return response.text


def embedding_index_operator() -> str:
    if exec_local:
        return "<=>"

    if 'nuclio' in model_settings:
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        response = requests.get(url)
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_encode(input_text: str, verbose: bool = False) -> List[float]:
    if exec_local:
        model = _MODEL_CACHE.get(huggingface_path)
        embeddings = model.encode([input_text], batch_size=128, show_progress_bar=False)
        return embeddings[0].tolist()

    if 'nuclio' in model_settings:
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        payload = {"text": input_text}
        response = requests.post(url, json=payload)
        response.raise_for_status()  # raises on non-200
        return response.json()



def embedding_encode_batch(
        batch_index: int,
        batch: Iterable[Tuple[Any, Any]],
        verbose: bool = False
  ) -> List[Tuple[Any, List[float]]]:
  
    texts = [row_text for _, row_text in batch]
    row_ids = [row_id for row_id, _ in batch]

    if exec_local:
        model = _MODEL_CACHE.get(huggingface_path)

        if verbose:
            for i, (row_id, row_text) in enumerate(zip(row_ids, texts), 1):
                input_column_text = row_text[:40].replace('\n', '').replace('\r', '')
                print(f"[INFO] (batch {batch_index}, {i}/{len(batch)}) Updating vector for row id {row_id}: '{input_column_text}'")

        embeddings = model.encode(texts, batch_size=128, show_progress_bar=False)
        values = [[row_id, embedding.tolist()] for row_id, embedding in zip(row_ids, embeddings)]
        return values

    if 'nuclio' in model_settings:
        print(f"embedding_encode_batch: {row_ids}")
        url = urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name)
        payload = {
            "index": batch_index,
            "batch": [[row_id, row_text] for row_id, row_text in zip(row_ids, texts)]
        }
        print(f"embedding_encode_batch: {payload}")
        response = requests.post(url, json=payload)
        print(f"response: {response.json()}")
        response.raise_for_status()  # raises on non-200
        return response.json()




if os.getenv("NUCLIO"):
    def handler(context, event):
        path = event.path
        method = event.method

        if path == "/embedding_label" and method == "GET":
            return context.Response(
                body=embedding_label(),
                headers={},
                content_type="text/plain",
                status_code=200
            )

        if path == "/embedding_description" and method == "GET":
            return context.Response(
                body=embedding_description(),
                headers={},
                content_type="text/plain",
                status_code=200
            )

        if path == "/embedding_dim" and method == "GET":
            return context.Response(
                body=embedding_dim(),
                headers={},
                content_type="text/plain",
                status_code=200
            )

        if path == "/embedding_index_opclass" and method == "GET":
            return context.Response(
                body=embedding_index_opclass(),
                headers={},
                content_type="text/plain",
                status_code=200
            )

        if path == "/embedding_index_operator" and method == "GET":
            return context.Response(
                body=embedding_index_operator(),
                headers={},
                content_type="text/plain",
                status_code=200
            )

        if path == "/embedding_encode" and method == "POST":
            body = event.body
            context.logger.info(f"event.body: {body}")

            input_text = body["text"]
            result = embedding_encode(input_text)

            return context.Response(
                body=json.dumps(result),
                headers={},
                content_type="application/json",
                status_code=200
            )


        if path == "/embedding_encode_batch" and method == "POST":
            body = event.body
            context.logger.info(f"event.body: {body}")

            batch_index = body['index']
            batch = body["batch"]
            result = embedding_encode_batch(batch_index, batch)

            return context.Response(
                body=json.dumps(result),
                headers={},
                content_type="application/json",
                status_code=200
            )


        return context.Response(
            body="not found",
            headers={},
            content_type="text/plain",
            status_code=404
        )


