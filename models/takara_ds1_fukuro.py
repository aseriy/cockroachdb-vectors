import textwrap
from typing import Iterable, List, Tuple, Any
from openai import OpenAI
import tiktoken
import yaml
from pathlib import Path


config_path = Path(__file__).resolve().parent.parent / "config.yaml"
config = None
with open(config_path, "r") as file:
    config = yaml.safe_load(file)

model_settings = next(
    item[Path(__file__).stem] 
    for item in config['models'] 
    if isinstance(item, dict) and Path(__file__).stem in item
)

_client = OpenAI(
                    api_key = model_settings['api_key'],
                    base_url = model_settings['base_url']
                )
_MODEL = model_settings['model']


def embedding_label() -> str:
    return "Takara-DS1/ds1-fukuro"


def embedding_description() -> str:
    return textwrap.dedent(
        """
        Takara-DS1/ds1-fukuro
        """
    ).strip()


def embedding_dim() -> int:
    return 1024


def embedding_index_opclass() -> str:
    return "vector_cosine_ops"


def embedding_index_operator() -> str:
    return "<=>"
    

def embedding_encode(input_text: str, verbose: bool = False) -> List[float]:
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

    texts = [row_text for _, row_text in batch]

    # We're within the token limits, go on...
    row_ids = [row_id for row_id, _ in batch]
    
    if verbose:
        for i, (row_id, row_text) in enumerate(zip(row_ids, texts), 1):
            input_column_text = row_text[:40].replace('\n', '').replace('\r', '')

    response = _client.embeddings.create(
        model=_MODEL,
        input=texts
    )

    embeddings = [data.embedding for data in response.data]
    
    values = [(row_id, embedding) for row_id, embedding in zip(row_ids, embeddings)]

    return values
