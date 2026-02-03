# CockroachDB Vector Embedding Toolkit

This repository provides a developer-focused toolkit for adding and experimenting with vector embeddings directly inside existing CockroachDB tables. It shows how to generate, store, index, and query embeddings alongside relational data—without introducing a separate vector database or re-architecting your system. The tools are designed to let engineers and data practitioners prototype similarity search and vector-backed workflows on real application data using pluggable embedding models.

These tools show how CRDB supports vector-backed workflows inside an existing system without architectural sprawl.


## How it works

The workflow is intentionally simple and builds on an existing CockroachDB schema.

### 1. Start with an existing table and column
The tool assumes you already have application data in CockroachDB (for example, a passage or description column). No data migration or new system is required.

### 2. Add a vector column alongside the data
When you run vectorize.py, the script:

- Discovers the table’s primary key
- Creates a companion vector column (for example, passage_vector) if it does not already exist
- Creates a vector index on that column

The original table structure and data remain unchanged.

### 3. Generate embeddings in place
Rows with a `NULL` vector column are processed in batches:

- The selected encoding model converts each row’s value into a vector
- The resulting vectors are written back to the same table, keyed by the original primary key

This makes embedding generation idempotent and safe to resume or re-run.

### 4. Use pluggable encoding models
Encoding logic is isolated from the pipeline:

- The main script orchestrates batching, retries, and database writes
- Each model module implements a small, well-defined interface:

    1. returns vectors for a batch of rows
    2. reports the embedding dimension it produces

This allows different models to be swapped in without changing the core workflow.

### 5. Query by similarity
Once vectors are populated and indexed, the table can be queried using vector similarity:

- Provide a value (for example, a sentence)
- Encode it using the same model
- Retrieve the most similar rows using vector distance operators

Similarity search happens directly inside CockroachDB, alongside normal SQL queries.


Script `vectorize.py` accomplishes the following:

1. given an existing table and an existing column, it creates, if not exists, a shodow vector column that stores an embedding based on the specified column.
2. It create a vector index on this vector column.
3. It uses a specified encoding model, such as HuggingFace Sentence Transformer, to generated an embedding for each row.

The script is design as a plug-n-play encoding model framework. the main script orchestarates the data pipeline in a encoding model agnostic way, while delegaing the actual encoding to the specific model. Each model is wrapped into a module under the `modules` directory and implements the pre-defined interface that performance the two main functions:

1. given a batch of tuples (PK, Value-to-be-encoded), it encodes each tuple's value and returns a batch of tuples (PK, Vector)
2. provides the dimension of the vector type that the model generates which is used by the main script to properly create the vector column


`vectorize.py` allows to:

1. list all available encoding models
2. encode the selected column in the specificed table
3. perform a vector search in the table based on the provided value, e.g. a sentence.


