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

    # print(json.dumps(ranges, indent=2))

    n_ranges = x_parser(ranges)
    for r in n_ranges:
        print(r)


    index_sizes = calc_index_bytes(
        get_table_id(conn_pool, args['table']),
        get_index_id(conn_pool, args['table']),
        n_ranges
    ) 

    print(json.dumps(index_sizes, indent=2))

    return None




# Scenario	Start Key	End Key	Your Current Logic
# Normal	/Table/131/1/...	/Table/131/1/...	Covered
# Bridge	/Table/131/1/...	/Table/131/2/...	Covered
# Gap/Shared	/Table/131/1/...	/Table/131/5/...	Covered
# Sentinel	<TableMin>	<TableMax>	Covered
# Bleed	<before:...>	<after:...>	Covered
# Literal NULL	NULL	/Table/...	NOT Covered


def _extract_table_index(key: str) -> tuple[int | None, int | None]:
    # Regex looks for /Table/ID and optionally /IndexID
    _TABLE_RE = re.compile(r'/Table/(\d+)(?:/(\d+))?')
    match = _TABLE_RE.search(key)
    
    if not match:
        return None, None

    table_id = int(match.group(1))
    index_raw = match.group(2)
    
    # Return index_id as None if it's missing in the key string
    index_id = int(index_raw) if index_raw is not None else None

    return table_id, index_id




def _normalize_key(key: str, fallback_table_id: int | None) -> list[int | None]:
    # 1. Handle Symbolic Start
    if '<TableMin>' in key:
        return [fallback_table_id, 1]

    # 2. Handle Symbolic End
    if '<TableMax>' in key:
        return [fallback_table_id, None]

    # 3. Extract IDs - index_id will be None if not in string
    table_id, index_id = _extract_table_index(key)

    # 4. Use fallback if the key is a boundary without a Table ID
    if table_id is None:
        table_id = fallback_table_id

    # No more raises. Return what we have for the estimation phase.
    return [table_id, index_id]




def x_parser(input: list[list[str, str, int]]) -> list[list[list[int | None], list[int | None], int]]:
    out = []

    for from_key, to_key, value in input:
        # Pre-extract to get fallback context for symbolic boundaries
        from_table_id, _ = _extract_table_index(from_key)
        to_table_id, _ = _extract_table_index(to_key)

        # Normalize using the other side as a fallback if one side is <TableMin/Max>
        from_boundary = _normalize_key(from_key, fallback_table_id=to_table_id)
        to_boundary = _normalize_key(to_key, fallback_table_id=from_table_id)

        out.append([from_boundary, to_boundary, value])

    return out




def calc_index_bytes(
        table_id: int,
        index_ids: list[int],
        ranges: list[list] # [ [from_t, from_i], [to_t, to_i], size ]
    ) -> dict[int, int]:

    out = {index_id: 0 for index_id in index_ids}

    for (from_table, from_idx), (to_table, to_idx), size in ranges:
        matched = []
        
        # Treat None in the starting index as 0 (start of table)
        f_idx = from_idx if from_idx is not None else 0

        # Case A: Range is entirely within our table
        if from_table == table_id and to_table == table_id:
            if to_idx is None: # Ends at <TableMax>
                matched = [i for i in index_ids if i >= f_idx]
            else:
                matched = [i for i in index_ids if f_idx <= i <= to_idx]

        # Case B: Range starts in our table but ends in another
        elif from_table == table_id:
            matched = [i for i in index_ids if i >= f_idx]

        # Case C: Range starts in a previous table but ends in ours
        elif to_table == table_id:
            if to_idx is None: # Covers the whole table up to Max
                matched = index_ids
            else:
                matched = [i for i in index_ids if i <= to_idx]

        # Case D: Super-range that completely swallows our table
        elif from_table < table_id < to_table:
            matched = index_ids

        for i in matched:
            out[i] += size

    return out



