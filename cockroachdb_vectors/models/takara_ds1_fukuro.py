import textwrap
from typing import Iterable, List, Tuple, Any
from openai import OpenAI
import tiktoken
import yaml
from pathlib import Path
import os
import json
import requests
from urllib.parse import urljoin, urlparse
from requests.auth import HTTPBasicAuth
import urllib3
import inspect


exec_local = True
_client = None
_MODEL = None
MAX_BATCH_SIZE = 32

if not os.getenv("NUCLIO"):
    config = None
    config_path = Path.cwd().joinpath("config.yaml")
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)

    model_settings = next(
        item[Path(__file__).stem] 
        for item in config['models'] 
        if isinstance(item, dict) and Path(__file__).stem in item
    )

    if 'nuclio' in model_settings:
        exec_local = False

        url_parsed = urlparse(model_settings['nuclio']['url'])
        if url_parsed.scheme == "https":
            if model_settings['nuclio'].get('username') \
                and model_settings['nuclio'].get('password'):

                model_settings['nuclio']['auth'] = HTTPBasicAuth(
                            model_settings['nuclio']['username'],
                            model_settings['nuclio']['password']
                        )

                if not model_settings['nuclio'].get('verify'):
                    model_settings['nuclio']['verify'] = False

                if not model_settings['nuclio']['verify']:
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    else:
        _client = OpenAI(
                            api_key = model_settings['api_key'],
                            base_url = model_settings['base_url']
                        )
        _MODEL = model_settings['model']


else:
    _client = OpenAI(
                        api_key = "xxx",
                        base_url = 'http://localhost:9090'
                    )

    _MODEL = 'ds1-fukuro'


# enf if
#





def embedding_label() -> str:
    if exec_local:
        return "Takara-DS1/ds1-fukuro"

    if 'nuclio' in model_settings:
        response = requests.get(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"}
                    )
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_description() -> str:
    if exec_local:
        return textwrap.dedent(
            """
            Takara-DS1/ds1-fukuro
            https://ds1.takara.ai/capabilities/text-embeddings.html
            """
        ).strip()

    if 'nuclio' in model_settings:
        response = requests.get(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"}
                    )
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_dim() -> int:
    if exec_local:
        return 1024

    if 'nuclio' in model_settings:
        response = requests.get(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"}
                    )
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_index_opclass() -> str:
    if exec_local:
        return "vector_ip_ops"

    if 'nuclio' in model_settings:
        response = requests.get(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"}
                    )
        response.raise_for_status()  # raises on non-200
        return response.text



def embedding_index_operator() -> str:
    if exec_local:
        return "<#>"
    
    if 'nuclio' in model_settings:
        response = requests.get(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"}
                    )
        response.raise_for_status()  # raises on non-200
        return response.text




def embedding_encode(input_text: str, verbose: bool = False) -> List[float]:
    if exec_local:
        response = _client.embeddings.create(
            model=_MODEL,
            input=input_text
        )
        return response.data[0].embedding

    if 'nuclio' in model_settings:
        response = requests.post(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"},
                        json = {"text": input_text}
                    )
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
        values = []
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch_texts = texts[i:i + MAX_BATCH_SIZE]
            batch_row_ids = row_ids[i:i + MAX_BATCH_SIZE]
            response = _client.embeddings.create(
                model=_MODEL,
                input=batch_texts
            )
            embeddings = [data.embedding for data in response.data]
            values.extend([(row_id, embedding) for row_id, embedding in zip(batch_row_ids, embeddings)])
        return values



    if 'nuclio' in model_settings:
        response = requests.post(
                        urljoin(model_settings['nuclio']['url'], inspect.currentframe().f_code.co_name),
                        auth = model_settings['nuclio']['auth'],
                        verify = False,
                        headers = {"Host": "nuclio.takara"},
                        json = {
                            "index": batch_index,
                            "batch": [[row_id, row_text] for row_id, row_text in zip(row_ids, texts)]
                        }
                    )
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

