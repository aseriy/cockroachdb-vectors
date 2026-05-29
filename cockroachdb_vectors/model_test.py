import click
import importlib
import json
from typing import Iterable, Tuple, Any
from operations.model import is_valid_model


_model = None


def test_embedding_label():
    global _model
    return _model.embedding_label()


def test_embedding_description():
    global _model
    return _model.embedding_description()


def test_embedding_dim():
    global _model
    return _model.embedding_dim()


def test_embedding_encode(input_text: str):
    global _model
    return _model.embedding_encode(input_text, True)


def test_embedding_encode_batch(batch: Iterable[Tuple[Any, Any]]):
    global _model
    return _model.embedding_encode_batch(0, batch, True)




@click.command()
@click.argument("model")
def main(model: str):
    if not is_valid_model(model):
        raise RuntimeError(f"Invalid embedding model {model}")

    print(f"Testing model: {model}")
    print()

    global _model
    _model = importlib.import_module(f"models.{model}")

    
    print("embedding_label()")
    print("-----------------")
    print(test_embedding_label())
    print()


    print("embedding_description()")
    print("-----------------------")
    print(test_embedding_description())
    print()


    print("embedding_dim()")
    print("---------------")
    print(test_embedding_dim())
    print()


    input_text = "CockroachDB is a source-available distributed SQL database management system developed by Cockroach Labs."
    print(f"embedding_encode(\"{input_text}\")")
    print("------------------")
    print(test_embedding_encode(input_text))
    print()


    input_batch: Iterable[Tuple[int, str]] = (
        (0, "zero zero zero zero zero"),
        (1, "one one one one one one"),
        (2, "two two two two two two")
    )
    print(f"embedding_encode_batch(\"{input_batch}\")")
    print("--------------------------------")
    for b in test_embedding_encode_batch(input_batch):
        print(b)
    print()


if __name__ == "__main__":
    main()
