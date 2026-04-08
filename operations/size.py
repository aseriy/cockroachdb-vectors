import atexit
import importlib
import json
import re
from typing import Any, Sequence
from psycopg2.pool import SimpleConnectionPool
from .model import is_valid_model
from .common import (
    build_conn_kwargs,
    main_get_conn,
    get_table_id,
    get_index_id
)



def run_size(args: dict):
    verbose = args['verbose']
    print(args)


    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    index_name = f"{args['table']}_{args['embedding']}_idx"
    index_name = "passage_passage_tsv_id_null_idx"

    index_id = get_index_id(conn_pool, args['table'], index_name)
    print(f"{index_name}: {index_id}")

    # Now pull the list of ranges with disk usage
    query = f"""
        SELECT                                                  
            start_key,
            end_key,
            (span_stats::JSONB ->> 'approximate_disk_bytes')::INT
        FROM
            [SHOW RANGES FROM TABLE {args['table']} WITH DETAILS]
    """

    ranges = []

    conn = main_get_conn(conn_pool)
    with conn.cursor() as cur:
        cur.execute(query)
        result = cur.fetchall()

    for r in result:
        ranges.append(r)

    conn_pool.putconn(conn)

    print(json.dumps(ranges, indent=2))

    n_ranges = x_parser(ranges)
    for r in n_ranges:
        print(r)


    return None





_TABLE_RE = re.compile(r'/Table/(\d+)(?:/(\d+))?')


def _extract_table_index(key: str) -> tuple[int | None, int | None]:
    match = _TABLE_RE.search(key)
    if not match:
        return None, None

    table_id = int(match.group(1))
    index_raw = match.group(2)
    index_id = 1 if index_raw is None else int(index_raw)

    return table_id, index_id


def _normalize_key(key: str, fallback_table_id: int | None) -> list[int | None]:
    if '<TableMin>' in key:
        if fallback_table_id is None:
            raise ValueError(f'Cannot resolve table_id for key={key!r}')
        return [fallback_table_id, 1]

    if '<TableMax>' in key:
        if fallback_table_id is None:
            raise ValueError(f'Cannot resolve table_id for key={key!r}')
        return [fallback_table_id, None]

    table_id, index_id = _extract_table_index(key)
    if table_id is None or index_id is None:
        raise ValueError(f'Unrecognized boundary key={key!r}')

    return [table_id, index_id]


def x_parser(input: Sequence[Sequence[Any]]) -> list[list[Any]]:
    out: list[list[Any]] = []

    for row in input:
        if len(row) != 3:
            raise ValueError(f'Expected 3 elements per row, got row={row!r}')

        from_key, to_key, value = row

        if not isinstance(from_key, str) or not isinstance(to_key, str):
            raise TypeError(f'Boundary keys must be strings, got row={row!r}')

        from_table_id, _ = _extract_table_index(from_key)
        to_table_id, _ = _extract_table_index(to_key)

        from_boundary = _normalize_key(from_key, fallback_table_id=to_table_id)
        to_boundary = _normalize_key(to_key, fallback_table_id=from_table_id)

        out.append([from_boundary, to_boundary, value])

    return out
