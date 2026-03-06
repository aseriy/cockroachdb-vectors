from psycopg2.pool import SimpleConnectionPool
import importlib
import re
from .model import is_valid_model
import atexit
from .common import (
    build_conn_kwargs,
    main_get_conn,
    get_primary_key_column,
    get_column_type
)


model = None


def is_vector_column(pool, table_name, vector_column, vector_dim, verbose=False) -> bool:
    """Checks if the vector column exists and or the correct type/dimensionality.

    Args:
        None

    Returns:
        True if the column exists, of type VECTOR(X), where X is model specific dimentions.
        False if the column doesn't exist.

    If a column with the specified name found but has wrong dimnetionality, an exception is raised.
    """

    vector_column_ok = False

    column_type = get_column_type(pool, table_name, vector_column)

    if column_type:
        if 'vector' not in column_type:
            raise RuntimeError(f"Column {vector_column} exists but is not of type VECTOR.")

        if not re.match(rf"^vector\({vector_dim}\)$", column_type):
            raise RuntimeError(f"Column {vector_column} is {column_type} but must be VECTOR({vector_dim}).")

        vector_column_ok = True

        if verbose:
            print(f"[INFO] Column {vector_column} {column_type} already exists")


    return vector_column_ok




def ensure_vector_column(pool, table_name, pk, output_column, dry_run=False, verbose=False):
    sql = []
    vector_dim = model.embedding_dim()

    if not is_vector_column(pool, table_name, output_column, vector_dim, verbose):
        sql.append(
            f"""
                ALTER TABLE "{table_name}"
                ADD COLUMN "{output_column}" VECTOR({vector_dim})
            """
        )


    conn = main_get_conn(pool)

    sql.append(f'''
                CREATE VECTOR INDEX IF NOT EXISTS "{table_name}_{output_column}_idx"
                ON "{table_name}"("{output_column}" {model.embedding_index_opclass()})
                WHERE "{output_column}" IS NOT NULL
                ''')
    sql.append(f'''
                CREATE INDEX IF NOT EXISTS "{table_name}_{output_column}_{pk}_null_idx"
                ON "{table_name}"("{pk}" ASC)
                WHERE "{output_column}" IS NULL
            '''
    )
    sql.append(f'''
                CREATE INDEX IF NOT EXISTS "{table_name}_{output_column}_{pk}_not_null_idx"
                ON "{table_name}"("{pk}" ASC)
                WHERE "{output_column}" IS NOT NULL
            '''
    )

    for stmt in sql:
        with conn.cursor() as cur:
            if dry_run:
                print(f"[DRY RUN] Would execute: {stmt}")
            else:
                cur.execute(stmt)


    pool.putconn(conn)




def run_instrument(args: dict):
    global model
    model = importlib.import_module(f"models.{args['model']}")

    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    primary_key, primary_key_type = get_primary_key_column(conn_pool, args['table'])
    ensure_vector_column(
        conn_pool,
        args['table'],
        primary_key,
        args['embedding'],
        False,
        args['verbose']
    )

    return None

