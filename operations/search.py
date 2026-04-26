import atexit
import importlib
import textwrap
from jinja2 import Template
from psycopg2.pool import SimpleConnectionPool
from .model import is_valid_model
from .common import build_conn_kwargs, main_get_conn, get_primary_key_column

model = None

search_tmpl = \
    """
        SELECT
            {{ primary_key }},
            {{ source }},
            ROUND({{ embedding }} {{ idxop }} {{ query }}::VECTOR({{ vector_dim }}), 6) AS distance
        FROM {{ table }}
        AS OF SYSTEM TIME follower_read_timestamp()
        WHERE {{ embedding }} IS NOT NULL
        ORDER BY {{ embedding }} {{ idxop }} {{ query }}::VECTOR({{ vector_dim }})
        LIMIT {{ limit }}
    """
search_tmpl = textwrap.dedent(search_tmpl).strip()

emit_note = \
    """
        Note:
        '%s' are positional parameters. Bind in order:
            1) query vector,
            2) same query vector,
            3) limit.
        Adjust syntax for your client library if needed.
    """
emit_note = textwrap.dedent(emit_note).strip()


def run_search(args: dict):
    verbose = args['verbose']

    if not is_valid_model(args['model']):
        raise RuntimeError(f"Invalid embedding model {args['model']}")

    global model
    model = importlib.import_module(f"models.{args['model']}")

    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    primary_key, primary_key_type = get_primary_key_column(conn_pool, args['table'])
    if verbose:
        print(f"[INFO] PK: {primary_key} ({primary_key_type})\n")

    vector = model.embedding_encode(args['text'], args['verbose'])
    vector_dim = model.embedding_dim()
    vector_param = "[" + ",".join(str(x) for x in vector) + "]"
    idxop = model.embedding_index_operator()

    query_tmpl = search_tmpl.replace("{{ limit }}", "%s")
    query_tmpl = query_tmpl.replace("{{ query }}", "%s")

    template = Template(query_tmpl)
    query = textwrap.dedent(
        template.render(
            table = args['table'],
            primary_key = primary_key,
            source = args['source'],
            embedding = args['embedding'],
            vector_dim = vector_dim,
            idxop = idxop
        )
    )
    print(f"{query}\n")
    print(f"{emit_note}\n")

    conn = main_get_conn(conn_pool)
    with conn.cursor() as cur:
        cur.execute(query, (vector_param,vector_param, args['limit']))
        result = cur.fetchall()

    for r in result:
        pk, src, dist = r
        print(f"{dist} --> {pk}")
        print(f"{src}")
        print()

    conn_pool.putconn(conn)

    return None



def run_emit(args: dict):
    verbose = args['verbose']
    sample = args['sample']

    if not is_valid_model(args['model']):
        raise RuntimeError(f"Invalid embedding model {args['model']}")

    global model
    model = importlib.import_module(f"models.{args['model']}")

    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    primary_key, primary_key_type = get_primary_key_column(conn_pool, args['table'])

    vector_param = None
    if sample:
        vector = model.embedding_encode(sample, verbose)
        vector_param = "[" + ",".join(str(x) for x in vector) + "]"

    vector_dim = model.embedding_dim()
    idxop = model.embedding_index_operator()

    if sample:
        query_tmpl = search_tmpl.replace("{{ query }}", f"'{str(vector_param)}'")
        query_tmpl = query_tmpl.replace("{{ limit }}", str(args['limit']))
    else:
        query_tmpl = search_tmpl.replace("{{ limit }}", "%s")
        query_tmpl = query_tmpl.replace("{{ query }}", "%s")

    template = Template(query_tmpl)
    query = textwrap.dedent(
        template.render(
            table = args['table'],
            primary_key = primary_key,
            source = args['source'],
            embedding = args['embedding'],
            vector_dim = vector_dim,
            idxop = idxop
        )
    )
    print(f"{query}\n")
    if not sample:
        print(f"{emit_note}\n")

