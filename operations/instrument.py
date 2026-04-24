from psycopg2.pool import SimpleConnectionPool
import importlib
import re
import json
import textwrap
from jinja2 import Template
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
            (
                f"[INFO] Adding new column {output_column} VECTOR({vector_dim})",
                f"""
                    ALTER TABLE "{table_name}"
                    ADD COLUMN "{output_column}" VECTOR({vector_dim})
                """
            )
        )

    sql.append(
        (
            f"[INFO] Creating vector index",
            f'''
            CREATE VECTOR INDEX IF NOT EXISTS "{table_name}_{output_column}_idx"
            ON "{table_name}"("{output_column}" {model.embedding_index_opclass()})
            WHERE "{output_column}" IS NOT NULL
            '''
        )
    )
    sql.append(
        (
            f"[INFO] Creating index to accelerate locating rows with no embeddings",
            f'''
                CREATE INDEX IF NOT EXISTS "{table_name}_{output_column}_{pk}_null_idx"
                ON "{table_name}"("{pk}" ASC)
                WHERE "{output_column}" IS NULL
            '''
        )
    )
    sql.append(
        (
            f"[INFO] Creating index to rows considered in vector searches",
            f'''
                CREATE INDEX IF NOT EXISTS "{table_name}_{output_column}_{pk}_not_null_idx"
                ON "{table_name}"("{pk}" ASC)
                WHERE "{output_column}" IS NOT NULL
            '''
        )
    )

    conn = main_get_conn(pool)

    for stmt in sql:
        with conn.cursor() as cur:
            print(stmt[0])
            if dry_run:
                print(f"[DRY RUN] Would execute: {stmt[1]}")
            else:
                cur.execute(stmt[1])

    pool.putconn(conn)




def drop_vector_column(
            pool, table_name, pk, output_column,
            green_idx=False, green_embed=False,
            dry_run=False, verbose=False
        ):
    sql = []
    vector_dim = model.embedding_dim()

    if green_idx:
        sql.append(
            (
                f"[INFO] Dropping vector index",
                f'''
                DROP INDEX IF EXISTS "{table_name}_{output_column}_idx"
                '''
            )
        )
        sql.append(
            (
                f"[INFO] Dropping index to accelerate locating rows with no embeddings",
                f'''
                    DROP INDEX IF EXISTS "{table_name}_{output_column}_{pk}_null_idx"
                '''
            )
        )
        sql.append(
            (
                f"[INFO] Dropping index to rows considered in vector searches",
                f'''
                    DROP INDEX IF EXISTS "{table_name}_{output_column}_{pk}_not_null_idx"
                '''
            )
        )

    if green_embed:
        if is_vector_column(pool, table_name, output_column, vector_dim, verbose):
            sql.append(
                (
                    f"[INFO] Dropping vector column {output_column} VECTOR({vector_dim})",
                    f"""
                        ALTER TABLE "{table_name}" DROP COLUMN "{output_column}"
                    """
                )
            )


    conn = main_get_conn(pool)

    for stmt in sql:
        with conn.cursor() as cur:
            print(stmt[0])
            if dry_run:
                print(f"[DRY RUN] Would execute: {stmt[1]}")
            else:
                cur.execute(stmt[1])

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

    trigger_config = read_trigger_function(conn_pool, args['table'])

    config = update_trigger_func_add_column(trigger_config, args['table'], args['source'], args['embedding'])
    trg_func_sql = update_trigger_sql(config, args['table'])
    install_trigger(conn_pool, trg_func_sql)

    return None



def run_cleanup(args: dict):
    global model
    model = importlib.import_module(f"models.{args['model']}")

    green_idx, green_embed = cleanup_confirm(args['table'], args['source'], args['embedding'])

    # TODO: check if the vector column exists. User may specify a non-existent column.
    #       Actually both, source and embedding.

    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    trigger_config = read_trigger_function(conn_pool, args['table'])
    config = update_trigger_func_drop_column(trigger_config, args['table'], args['source'], args['embedding'])
    
    trg_func_sql = update_trigger_sql(config, args['table'], drop=True)
    install_trigger(conn_pool, trg_func_sql)

    primary_key, primary_key_type = get_primary_key_column(conn_pool, args['table'])
    drop_vector_column(
        conn_pool,
        args['table'],
        primary_key,
        args['embedding'],
        green_idx, green_embed,
        False,
        args['verbose']
    )

    return None



def cleanup_confirm(table_name, source_col, vector_col):
    drop_indexes, drop_column = False, False

    prompt = textwrap.dedent(f"""
        You're about to remove the vector embeddings associated with {table_name}.{source_col}.
        1. Disable resetting {table_name}.{vector_col} when {table_name}.{source_col} is updated.
        2. Drop all indexes that accelerate embedding and search operations.
        3. Drop the vector column {table_name}.{source_col}.

    """)

    print(prompt)

    y_or_n = input("Drop indexes?       [y/N]: ").strip().lower()
    if y_or_n == 'y':
        drop_indexes = True

    if not drop_indexes:
        print(f"[INFO] Indexes and vector column will NOT be dropped")

    else:
        y_or_n = input ("Drop vector column? [y/N]: ").strip().lower()
        if y_or_n == 'y':
            drop_column = True

    return drop_indexes, drop_column




def install_trigger(pool, sql):
    conn = main_get_conn(pool)

    with conn.cursor() as cur:
        cur.execute(sql[0])
        if cur.fetchone()[0]:
            print(f"[INFO] Dropping trigger...")
            cur.execute(sql[1])

        if sql[2]:
            print(f"[INFO] Updating trigger function...")
            cur.execute(sql[2])

        if sql[3]:
            print(f"[INFO] Creating trigger...")
            cur.execute(sql[3])


    pool.putconn(conn)



def update_trigger_sql(config, table_name, drop = False):
    sql_tmpl = [
        """
            SELECT count(*) FROM pg_catalog.pg_trigger
            WHERE tgname='clear_vector_on_update_{{ table_name }}'; 
        """,
        """
            DROP TRIGGER IF EXISTS clear_vector_on_update_{{ table_name }}
            ON {{ table_name }};
        """
    ]

    if config:
        sql_tmpl.append(
            """
                CREATE OR REPLACE FUNCTION clear_vector_on_update_{{ table_name }}()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$

                BEGIN
                    {% for item in config %}
                    IF (NEW).{{ item.input }} <> (OLD).{{ item.input }} THEN
                        {% for out in item.output %}NEW.{{ out }} := NULL;
                        {% endfor %}
                    END IF;

                    {% endfor %}
                    RETURN NEW;
                END;
                $$;
            """
        )
    else:
        sql_tmpl.append(None)

    
    if not drop:
        sql_tmpl.append(
            """
                CREATE TRIGGER clear_vector_on_update_{{ table_name }}
                BEFORE UPDATE ON {{ table_name }}
                FOR EACH ROW
                EXECUTE FUNCTION clear_vector_on_update_{{ table_name }}();
            """
        )
    else:
        sql_tmpl.append(None)
    

    sql = []
    for tmpl in sql_tmpl:
        if tmpl is not None:
            template = Template(tmpl)
            sql.append(
                textwrap.dedent(
                    template.render(
                        table_name=table_name, 
                        config=config
                    )
                )
            )
        else:
            sql.append(None)

    return sql




def update_trigger_func_add_column(config, table_name, source_column, vector_column):
    new_config = config

    match_source = [(i, c) for i, c in enumerate(config) if c['input'] == source_column]

    if match_source:
        i, c = match_source[0]
        output = c['output']
        if not vector_column in output:
            output.append(vector_column)
        new_config[i]['output'] = output

    else:
        new_config.append(
            {
                'input': source_column,
                'output': [vector_column]
            }
        )        


    return new_config



def update_trigger_func_drop_column(config, table_name, source_column, vector_column):
    new_config = config

    match_source = [(i, c) for i, c in enumerate(config) if c['input'] == source_column]

    if match_source:
        i, c = match_source[0]
        output = c['output']
        if vector_column in output:
            output.remove(vector_column)

        if not output:
            del new_config[i]
        else:
            new_config[i]['output'] = output

    return new_config




def read_trigger_function(pool, table_name) -> dict:
    trg_func_name = f"clear_vector_on_update_{table_name}"
    trg_func_body = None

    config = []

    func_list = None
    stmt = "SELECT function_name FROM [SHOW FUNCTIONS]"
    conn = main_get_conn(pool)
    with conn.cursor() as cur:
        cur.execute(stmt)
        func_list = [r[0] for r in cur.fetchall()]
    pool.putconn(conn)

    if not trg_func_name in func_list:
        return config

    stmt = f"""
            SELECT create_statement FROM [
                SHOW CREATE FUNCTION {trg_func_name}
            ]
        """  

    conn = main_get_conn(pool)
    with conn.cursor() as cur:
        cur.execute(stmt)
        trg_func_body = cur.fetchone()[0]
    pool.putconn(conn)

    # 1. Extract everything between $$ ... $$
    body_match = re.search(r'\$\$(.*?)\$\$', trg_func_body, re.DOTALL)
    if body_match:
        body = body_match.group(1)
        
        # 2. Find each IF ... END IF block
        # This captures the condition and the internal assignments
        blocks = re.findall(r'IF\s+(.*?)\s+THEN(.*?)\s+END IF;', body, re.DOTALL)
        
        for condition, assignments in blocks:

            # Extract the input column from (NEW).colname
            # Match handles both "(NEW).col" and "NEW.col"
            input_col = re.search(r'\(?NEW\)?\.(\w+)', condition, re.IGNORECASE)
            
            # Extract all output columns from "NEW.colname := NULL"
            output_cols = re.findall(r'NEW\.(\w+)\s*:=', assignments, re.IGNORECASE)
            
            if input_col and output_cols:
                config.append({
                    'input': input_col.group(1),
                    'output': output_cols
                })

    return config

