from urllib.parse import urlparse
from typing import Optional, Any
from psycopg2.extensions import connection


def build_conn_kwargs(db_url) -> dict[str, Any]:
    parsed = urlparse(db_url)
    return dict(
        dbname=parsed.path[1:],
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 26257,
        sslmode=(
            parsed.query.split("sslmode=")[1]
            if parsed.query and "sslmode=" in parsed.query
            else "require"
        )
    )


def main_get_conn(pool) -> connection:
    conn = pool.getconn()
    conn.autocommit = True
    return conn



def get_table_id(pool, table_name) -> int:
    conn = main_get_conn(pool)
    table_id = None

    query = f"""
        SELECT table_id                                         
        FROM crdb_internal.tables                               
        WHERE name = '{table_name}'
    """

    with conn.cursor() as cur:
        cur.execute(query)
        result = cur.fetchone()
        if result:
            table_id = result[0]

    pool.putconn(conn)

    return table_id



def get_index_id(pool, table_name, index_name = None) -> int | list[int]:
    conn = main_get_conn(pool)
    table_id = get_table_id(pool, table_name)
    index_id = None

    if table_id:
        query = f"""
            SELECT index_id
            FROM crdb_internal.table_indexes
            WHERE
                descriptor_name = '{table_name}'
        """

        if index_name:
            query += f"""
                    AND
                    index_name = '{index_name}'
            """

        with conn.cursor() as cur:
            cur.execute(query)
            if index_name:
                result = cur.fetchone()
                index_id = result[0]
            else:
                result = cur.fetchall()
                index_id = [r[0] for r in result]

    pool.putconn(conn)

    return index_id



def get_primary_key_column(pool, table_name) -> dict:
    conn = main_get_conn(pool)

    pk_result = None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.attname AS column_name,
                t.typname AS column_type
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid
             AND a.attnum = ANY(i.indkey)
            JOIN pg_type t
              ON a.atttypid = t.oid
            WHERE i.indrelid = %s::regclass
              AND i.indisprimary
            """,
            (table_name,)
        )
        pk_result = cur.fetchone()

    pool.putconn(conn)

    if not pk_result:
        raise RuntimeError(f"No primary key found for table '{table_name}'")

    pk_name, pk_type = pk_result
    return pk_name, pk_type



def get_column_type(
        pool,
        table_name: str,
        column_name: str
    ) -> Optional[str]:

    conn = main_get_conn(pool)

    sql = f'''
            SELECT
                CASE 
                    WHEN t.typname = 'vector' AND a.atttypmod > 0 THEN 'vector(' || a.atttypmod || ')'
                    ELSE format_type(a.atttypid, a.atttypmod)
                END AS full_type
            FROM pg_attribute a
            JOIN pg_type t ON a.atttypid = t.oid
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relname = %s AND a.attname = %s;
        '''

    column_type = None
    with conn.cursor() as cur:
        cur.execute(sql, (table_name, column_name))
        existing = cur.fetchone()
        if existing:
            column_type = existing[0]

    pool.putconn(conn)
    return column_type

