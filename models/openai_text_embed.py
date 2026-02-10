import textwrap
from typing import Iterable, List, Tuple, Any
from openai import OpenAI
import tiktoken
import yaml
from pathlib import Path


#
# Embedding Token Limits
# Valid for text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002 models
#
PER_STRING_TOKEN_LIMIT      = 8191
MAX_BATCH_SIZE              = 2048
TOTAL_TOKENS_PER_REQUEST    = 300000

MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536
}


config_path = Path(__file__).resolve().parent.parent / "config.yaml"
config = None
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

openai_settings = next(
    item[Path(__file__).stem] 
    for item in config['models'] 
    if isinstance(item, dict) and 'openai_text_embed' in item
)

_client = OpenAI(api_key=openai_settings['api_key'])
_MODEL = openai_settings['model']
_encoding = tiktoken.encoding_for_model(_MODEL)


def embedding_label() -> str:
    return "OpenAI Text Embedding API"


def embedding_description() -> str:
    return textwrap.dedent(
        """
        General-purpose text embedding model provided by OpenAI via hosted API.
        Optimized for semantic similarity, clustering, and retrieval tasks
        across a wide range of domains. Produces fixed-length dense float vectors;
        dimensionality depends on the selected OpenAI embedding model. Supports
        multilingual input.
        https://platform.openai.com/docs/guides/embeddings
        """
    ).strip()


# The dimensionality can be force to a lower number than MODEL_DIMENSIONS
# TODO: we may introduce a new API call like embedding_dim_set(dim) to force
#       the dimansionality for the models that allow for this, e.g. OpenAI
# response = client.embeddings.create(
#     model="text-embedding-3-large",
#     input="Your text here",
#     dimensions=1024  # Lowering from 3072 to 1024
# )
def embedding_dim() -> int:
    return MODEL_DIMENSIONS[_MODEL]



def embedding_encode(input_text: str, verbose: bool = False) -> List[float]:
    global _encoding
    token_integers = _encoding.encode(input_text)
    num_tokens = len(token_integers)

    if num_tokens > PER_STRING_TOKEN_LIMIT:
        raise RuntimeError(f"Input text length exceeds the API limit of {PER_STRING_TOKEN_LIMIT}")

    response = _client.embeddings.create(
        model=_MODEL,
        input=input_text
    )
    return response.data[0].embedding



def embedding_encode_batch(
        batch_index: int,
        batch: Iterable[Tuple[Any, Any]],
        verbose: bool = False
    ) -> List[Tuple[Any, List[float]]]:

    # OpenAI won't accept a batch that exceeds MAX_BATCH_SIZE
    if len(batch) > MAX_BATCH_SIZE:
        raise RuntimeError(f"Input batch size exceeds the API limit of {MAX_BATCH_SIZE}")


    texts = [row_text for _, row_text in batch]

    # Check if we're not violating the API token limits
    total_tokens = 0
    global _encoding
    for input_text in texts:
        token_integers = _encoding.encode(input_text)
        num_tokens = len(token_integers)
        
        if num_tokens > PER_STRING_TOKEN_LIMIT:
            raise RuntimeError(f"Input text length exceeds the API limit of {PER_STRING_TOKEN_LIMIT}")
        
        total_tokens += num_tokens
        if total_tokens > TOTAL_TOKENS_PER_REQUEST:
            raise RuntimeError(f"Number of token in the batch exceeds the API limit of {TOTAL_TOKENS_PER_REQUEST}")


    # We're within the token limits, go on...
    row_ids = [row_id for row_id, _ in batch]
    
    if verbose:
        for i, (row_id, row_text) in enumerate(zip(row_ids, texts), 1):
            input_column_text = row_text[:40].replace('\n', '').replace('\r', '')
            print(f"[INFO] (batch {batch_index}, {i}/{len(batch)}) Updating vector for row id {row_id}: '{input_column_text}'")

    response = _client.embeddings.create(
        model=_MODEL,
        input=texts
    )

    embeddings = [data.embedding for data in response.data]
    
    values = [(row_id, embedding) for row_id, embedding in zip(row_ids, embeddings)]

    return values
