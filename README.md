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


```bash
$ python3 vectorize.py embed -u postgresql://<user>:<pass>@<dbhost>:26257/<database>?sslmode=verify-full -t passage -i passage -o passage_vector -m hf_st_all_minilm_l6 -b 10 -n 1 -w 2 -v
[INFO] Column passage_vector already exists
[INFO] Run 1, Batch 1 starting (10 rows)
[INFO] (batch 1, 1/5) Updating vector for row id 02e2e3af-821e-4a3e-8115-ccb9d7042df9: 'Since the most expensive collection acti'
[INFO] (batch 1, 2/5) Updating vector for row id 02e2e580-b496-4ea3-9a70-ca1e13ffe7a3: 'And Jesus, knowing their thoughts, said '
[INFO] (batch 1, 3/5) Updating vector for row id 02e2fc69-a896-4046-8f7d-92042d97b0c9: 'Further Reading. A few good sources for '
[INFO] (batch 1, 4/5) Updating vector for row id 02e3095f-c8cd-4dd6-91e5-2c924bc55a48: 'See more results ». More examples. Her a'
[INFO] (batch 1, 5/5) Updating vector for row id 02e3101c-442e-43cf-a019-3a35e832bdae: 'In folklore the markhor is known to kill'
[INFO] (batch 1, 1/5) Updating vector for row id 02e313c9-d053-4a34-a9ef-daba8ad15eaf: 'Problem: One problem Father had in the s'
[INFO] (batch 1, 2/5) Updating vector for row id 02e3162f-288f-4238-aaad-189f4baa6d50: 'Not looking for Miami 305 area code info'
[INFO] (batch 1, 3/5) Updating vector for row id 02e31780-cfcd-4ab7-b9cc-fae0c5ac0fcc: 'Despite getting sent-off in the 1998 Wor'
[INFO] (batch 1, 4/5) Updating vector for row id 02e334f8-1212-4656-83f1-1411e8411397: 'The extra rigidity afforded by the tubes'
[INFO] (batch 1, 5/5) Updating vector for row id 02e34693-4372-482b-a332-0e35a62feb22: 'CONCERT REVIEWS: Alice Cooper and Cheap '
Done in 13.912834882736206 seconds
[INFO] Vectorization complete.
```


If the output vector column does not already exist, the script will create it automatically. The vector column’s dimensionality is derived from the selected embedding model (see the model subcommand below).

To keep the workflow simple and generic, the script only processes rows where the output vector column is `NULL`. There is no built-in mechanism to detect whether embeddings are out of date. If the source data in a row is updated, the corresponding vector column must be explicitly cleared (set to `NULL`) in order for embed to regenerate the embedding.


### `embed` Performance Options

The `embed` command is designed to efficiently generate embeddings while keeping database writes predictable and low-contention. To achieve this, embedding computation and database updates are intentionally decoupled.

At a high level:
- Embedding computation can run in parallel across multiple CPUs.
- Generated embeddings are collected into batches.
- Database updates are executed sequentially, in batches, to minimize write contention and maximize database efficiency.

The following options control this behavior.

### Batch size (-b, --batch-size)

The batch size defines how many rows are updated in a single database write batch. Each batch groups together a fixed number of newly generated embeddings before they are written back to CockroachDB.

Larger batches reduce the number of database write operations, while smaller batches reduce per-batch resource usage. Batch size affects database write behavior but does not control parallelism.

>[!NOTE]
> Since this is purposefully a non-production script, it doesn't prevent the input column from being updated while the embeddings are calculated. Your real-life production application may require this level of strictness.

### Parallel workers (-w, --workers)

The workers option controls how many embeddings are calculated in parallel. Each worker independently computes embeddings for input rows, allowing the embedding step to utilize multiple CPUs.

Parallelism applies only to embedding computation. Database updates remain single-threaded and batched to avoid write contention.

### Number of batches (-n, --num-batches)

The number of batches option limits how many batches are processed during a single invocation of embed. This provides a simple way to bound the amount of work performed before the command exits.

The total number of rows processed in one run is approximately the batch size multiplied by the number of batches.

### Continuous operation (-F, --follow)

When run with --follow, the embed command continues running until there are no remaining rows where the output vector column is NULL. The same batching and parallelism rules apply, but the process does not exit after a fixed number of batches.

This mode enables continuous vectorization as new rows are inserted, without introducing additional logic for detecting stale or out-of-date embeddings.



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

```bash
$ python3 vectorize.py search -u postgresql://<user>:<pass>@<dbhost>:26257/<database>?sslmode=verify-full -t passage -i passage -o passage_vector -m hf_st_all_minilm_l6 -l 10 -v "New York City is the financial capital of the world!"
[INFO] PK: id (uuid)

0.5445506274700036 --> 01cef214-02ff-4648-91f4-ab55031d3223
It pointed to the fact that New York spends more money per student than any other state - more than $18,000 per year - and yet ranks 39th in high school graduation rates. This is the kind of inflammatory rhetoric that The Wall Street Journal and The Washington Times routinely engage in.

0.5668426841340002 --> 013d665f-e68a-476f-ae24-3f139834f899
TOP banks in USA. JPMorgan Chase Bank, NA. Wells Fargo Bank, NA. Bank of America, NA. Citibank, NA. U.S. Bank NA. PNC Bank, NA. The Bank of New York Mellon. Capital One, NA.

0.5668426841340002 --> 014939ea-a998-42bf-88da-fff6ee017cf9
TOP banks in USA. JPMorgan Chase Bank, NA. Wells Fargo Bank, NA. Bank of America, NA. Citibank, NA. U.S. Bank NA. PNC Bank, NA. The Bank of New York Mellon. Capital One, NA.

0.6034485219881293 --> 02c437f2-a021-4b63-9f0c-6f85bc123afa
granddaddy of the many fine art museums in New York. Fast Facts & Information. Safety: New York is the largest city in the United States, and also is distinguished as having the lowest crime rate among the 25 largest American cities, according to the FBI Crime Report.

0.6072394549846538 --> 001da25f-eb02-4426-9c3a-19ad1e314b0f
Merrill Lynch Corporate Office & Headquarters. 4 World Financial Center 250 Vesey Street New York NY 10080.

0.6090512806742557 --> 02082f83-2a20-416b-a42b-20ab9e79308e
According to the Notice as at Sept. 30, 2002, registered national exchanges, include the American Stock Exchange, the Boston Stock Exchange, the Cincinnati Stock Exchange, the Chicago Stock Exchange, the NYSE, the Philadelphia Stock Exchange, and the Pacific Exchange, Inc.

0.6157920680541831 --> 0021d323-319c-4935-bf20-6666c3d9232d
Finance capital, in the constant drive to increase profit, uses technology to lower production costs by replacing human labour with machines and other labour-saving processes. Scientific and technological progress has become the source of increased exploitation and alienation of the working class.

0.6191794517101485 --> 02659fb0-63c7-48ae-bd48-8df78537d102
Since Colonial times Wall Street was the province of an elite few. That changed in the 1980s. Millions of Americans hitched their dreams to the stock market. America's economic tide rose in the 1980s, but more of the nation's wealth flowed to those who were already well-off.

0.6356513093605897 --> 019ebf8a-3578-4667-9f91-bf71b2d3957f
As tax season kicks off, NYC Free Tax Prep is ready | New York Amsterdam News: The new Black view.

0.6496077582356925 --> 00e3cea8-a9f2-4772-86b1-cfbf4ee40537
Cost of living data is from the Missouri Economic Research and Information Center. This is 24/7 Wall St.’s states doing the most (and least) to spread the wealth. Everyone Who Believes in God Should Watch This.

```


## Embedding Models

`vectorize.py` is design to decouple the vector embedding from the data pipeline / database mechanics. The vector encoding is delegate to the embedding model wrappers located in the `models` directory:

```bash
models/
models/__init__.py
models/hf_st_all_minilm_l6.py
```

The model will be referenced by the name of the wrapper file, i.e. `hf_st_all_minilm_l6`.

A model wrapper has to implement the following functions:

```python
def embedding_label() -> str
```

A short description of the model. This is what `vectorize.py model list` will show:

```bash
$ python3 vectorize.py model list
hf_st_all_minilm_l6	Hugging Face Sentence Transformer all-MiniLM-L6-v2
```

```python
def embedding_description() -> str
```

A long description of the model, including the dimensionality and anything else that's important to the user to know. This is displayed by `vectorize.py model desc f_st_all_minilm_l6`:

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

```python
def embedding_dim() -> int
```

Returns the dimensionality of the model. It's used by the script to create the vector output column if it doesn't exist.


```python
def embedding_encode(
        input_data: Any,
        verbose: bool = False
    ) -> List[float]
```

This function takes a single row's input column data to be encode, and return the resulting vector.

>[!NOTE]
> The input data may be of any type, not just text. The model needs to be aware of the data type it's embedding.


```python
def embedding_encode_batch(
        batch_index: int,
        batch: Iterable[Tuple[Any, Any]],
        verbose: bool = False
    ) -> List[Tuple[Any, List[float]]]
```

This function takes:

1. a batch index - this is for information purposes only and used to generate INFO message
2. a list of tuple where each tuple contains the primary key and the input column value. Both can be of any data type.

It returns a resulting list of PK-Embedding tuples.