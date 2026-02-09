import atexit
import importlib
from psycopg2.pool import SimpleConnectionPool
from .model import is_valid_model
from .common import build_conn_kwargs, main_get_conn, get_primary_key_column


model = None


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
        print(f"[INFO] PK: {primary_key} ({primary_key_type})")
        print()

    vector = model.embedding_encode(args['text'], args['verbose'])
    vector_param = "[" + ",".join(str(x) for x in vector) + "]"

    query = f"""
            SELECT
                {primary_key},
                {args['source']},
                {args['embedding']} <=> %s AS distance
            FROM {args['table']}
            AS OF SYSTEM TIME follower_read_timestamp()
            WHERE {args['embedding']} IS NOT NULL
            ORDER BY {args['embedding']} <=> %s
            LIMIT {args['limit']}
    """

    conn = main_get_conn(conn_pool)
    with conn.cursor() as cur:
        cur.execute(query, (vector_param,vector_param))
        result = cur.fetchall()

    for r in result:
        pk, src, dist = r
        print(f"{dist} --> {pk}")
        print(f"{src}")
        print()

    conn_pool.putconn(conn)

    return None

