# CockroachDB Vector Embedding Toolkit

This repository provides a developer-focused toolkit for adding and experimenting with vector embeddings directly inside existing CockroachDB tables. It shows how to generate, store, index, and query embeddings alongside relational data—without introducing a separate vector database or re-architecting your system. The tools are designed to let engineers and data practitioners prototype similarity search and vector-backed workflows on real application data using pluggable embedding models.

These tools show how CRDB supports vector-backed workflows inside an existing system without architectural sprawl.


## `vectorize.py`

At the center of the toolkit is the vectorize.py script. It exposes a simple CLI with three subcommands that map directly to the core functions of the toolkit: embedding data, inspecting models, and running similarity search.

>[!NOTE]
> This toolkit is intended for experimentation and prototyping. It favors simplicity and transparency over production-grade automation.


### `embed`

The `embed` subcommand generates vector embeddings for rows in an existing CockroachDB table and stores them alongside the original data.

At a high level, it:

- Reads values from a specified input column
- Generates embeddings using the selected encoding model
- Writes the resulting vectors into a specified output column

If the output vector column does not already exist, the script will create it automatically. The vector column’s dimensionality is derived from the selected embedding model (see the model subcommand below).

To keep the workflow simple and generic, the script only processes rows where the output vector column is `NULL`. There is no built-in mechanism to detect whether embeddings are out of date. If the source data in a row is updated, the corresponding vector column must be explicitly cleared (set to `NULL`) in order for embed to regenerate the embedding.


### `model`

The `model` subcommand provides visibility into the available embedding models supported by the toolkit. It does not interact with the database.

It supports two operations:

- `model list` lists all available encoding models
- `model desc <model>` describes a specific model in more detail, including properties such as embedding dimensionality

```bash
$ python3 vectorize.py model list
hf_st_all_minilm_l6	Hugging Face Sentence Transformer all-MiniLM-L6-v2
```

```bash
$ python3 vectorize.py model desc hf_st_all_minilm_l6
------------------------------------------------------
| Hugging Face Sentence Transformer all-MiniLM-L6-v2 |
------------------------------------------------------
General-purpose English sentence embedding model
based on MiniLM. Optimized for semantic similarity,
clustering, and retrieval tasks. Produces 384-dimensional
float vectors. Not multilingual.
https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

```

The `vectorize.py` script uses a pluggable model architecture. Encoding models are implemented as interchangeable modules with a small, well-defined interface. Instructions for adding new models are provided in a later section.


### `search`

The `search` subcommand performs semantic similarity search over rows that have already been vectorized.

Given an input text value, it:

- Encodes the text using the same embedding model used during `embed`
- Executes a vector similarity query directly inside CockroachDB
- Returns the closest matching rows based on vector distance

Similarity search runs entirely within the database and can be combined with standard SQL filtering and querying patterns.


