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
            ROUND({{ embedding }} {{ idxop }} %s::VECTOR({{ vector_dim }}), 6) AS distance
        FROM {{ table }}
        AS OF SYSTEM TIME follower_read_timestamp()
        WHERE {{ embedding }} IS NOT NULL
        ORDER BY {{ embedding }} {{ idxop }} %s::VECTOR({{ vector_dim }})
        LIMIT %s
    """
search_tmpl = textwrap.indent(textwrap.dedent(search_tmpl).strip(), '\t')


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

    template = Template(search_tmpl)
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

