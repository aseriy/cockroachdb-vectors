import atexit
import importlib
import json
import re
import humanize
from typing import Any, Sequence
from psycopg2.pool import SimpleConnectionPool
from rich.console import Console
from rich.table import Table
from rich.padding import Padding
from rich.align import Align
from .model import is_valid_model
from .common import (
    build_conn_kwargs,
    main_get_conn,
    get_table_id,
    get_index_id,
    get_column_type
)



def run_size(args: dict):
    verbose = args['verbose']
    
    display_results()
    return


    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    index_vector_name = f"{args['table']}_{args['embedding']}_idx"
    index_vector_id = get_index_id(conn_pool, args['table'], index_vector_name)

    index_id_null_name = f"{args['table']}_{args['embedding']}_id_null_idx"
    index_id_null_id = get_index_id(conn_pool, args['table'], index_id_null_name)

    index_id_not_null_name = f"{args['table']}_{args['embedding']}_id_not_null_idx"
    index_id_not_null_id = get_index_id(conn_pool, args['table'], index_id_not_null_name)



    v_col_type = get_column_type(conn_pool, args['table'], args['embedding'])
    print(f"vector column type: {v_col_type}")
    match = re.match(rf"^vector\((\d+)\)$", v_col_type)
    if not match:
        raise RuntimeError(f"Column {args['embedding']} is {v_col_type} but must be VECTOR().")

    vector_dim = int(match.group(1))
    print(f"vector dim: {vector_dim}")

    query = f"""
            SELECT count(*) FROM {args['table']}
            """

    row_cnt = 0
    conn = main_get_conn(conn_pool)
    with conn.cursor() as cur:
        cur.execute(query)
        row_cnt = cur.fetchone()[0]
    conn_pool.putconn(conn)
    print(f"row_cnt: {row_cnt}")

    embedding_space = vector_dim * 4 * row_cnt
    print(f"embedding space: {embedding_space} --> {humanize.naturalsize(embedding_space, gnu=True)}")

    table_space, index_space = calc_index_space(conn_pool, args['table'], index_vector_name)
    # print(json.dumps(index_space, indent=2))

    print(f"index: {index_vector_name} --> {index_vector_id} --> {humanize.naturalsize(index_space[index_vector_id], gnu=True)}")
    print(f"index: {index_id_null_name} --> {index_id_null_id} --> {humanize.naturalsize(index_space[index_id_null_id], gnu=True)}")
    print(f"index: {index_id_not_null_name} --> {index_id_not_null_id} --> {humanize.naturalsize(index_space[index_id_not_null_id], gnu=True)}")
    print(f"table: {table_space}")

    # Total extra space including the auxiliary indexes
    vector_space = embedding_space + index_space[index_vector_id] 
    toolkit_space = (
            vector_space +
            index_space[index_id_null_id] +
            index_space[index_id_not_null_id]
        )

    # Table space without the above
    table_space = table_space - toolkit_space

    # Vector space as a percentage of the initial table space
    vector_space_increase_ration = float(vector_space) / float(table_space)

    print(f"table: {humanize.naturalsize(table_space, gnu=True)}")
    print(f"vector: {humanize.naturalsize(vector_space, gnu=True)}")
    print(f"increase: {vector_space_increase_ration}")


    return None



def display_results():
    console = Console()

    # 💡 Move padding here (Row Padding, Column Padding)
    table = Table(
                    show_header=False,
                    pad_edge=False,
                    padding=0,
                    show_lines=True
                )

    table.add_column("1") 
    table.add_column("2") 
    table.add_column("3", justify="right") 

    table.add_row(
                    Padding("Initial table size", (0, 4, 0, 1)),
                    Padding("passage", (0, 4, 0, 1)),
                    Padding("6.8G", (0, 0, 0, 6))
                )
    table.add_row(
                    Padding("+ Vector column", (0, 4, 0, 1)),
                    Padding("passage_vector", (0, 4, 0, 1)),
                    Padding("5.3G", (0, 0, 0, 6)),
                )
    table.add_row(
                    Padding("+ Vector index", (0, 4, 0, 1)),
                    Padding("passage_passage_vector_idx", (0, 4, 0, 1)),
                    Padding("2.4G", (0, 0, 0, 6)),
                )
    table.add_row(
                    Padding("+ Toolkit indexes", (0, 4, 0, 1)),
                    Padding("\n".join([
                                "passage_passage_vector_id_null_idx",
                                "passage_passage_vector_id_not_null_idx"
                            ]),
                            (0, 4, 0, 1)),
                    Padding("\n".join(["17.6M", "479.0M"]), (0, 0, 0, 6))
                )
    table.add_row(
                    Padding("= Resulting table size", (0, 4, 0, 1)),
                    Padding("passage", (0, 4, 0, 1)),
                    Padding("6.8G", (0, 0, 0, 6))
                )
    table.add_row(
                    Padding(Align(">>>", align="right") , (0, 1, 0, 1)),
                    Padding(Align("Vector storage overhead", align="right"), (0, 1, 0, 1)),
                    Padding("14%", (0, 0, 0, 6))
                )
    table.add_row(
                    Padding(Align(">>>", align="right") , (0, 1, 0, 1)),
                    Padding(Align("Toolkit storage overhead", align="right"), (0, 1, 0, 1)),
                    Padding("0.1%", (0, 0, 0, 6))
                )

    console.print(table)





def calc_index_space(
                    pool: SimpleConnectionPool,
                    table_name: str,
                    index_vector_name: str,
                ) -> str:

    index_vector_id = get_index_id(pool, table_name, index_vector_name)

    # Now pull the list of ranges with disk usage
    query = f"""
        SELECT                                                  
            start_key,
            end_key,
            (span_stats::JSONB ->> 'approximate_disk_bytes')::INT
        FROM
            [SHOW RANGES FROM TABLE {table_name} WITH DETAILS]
    """

    ranges = []

    conn = main_get_conn(pool)
    with conn.cursor() as cur:
        cur.execute(query)
        result = cur.fetchall()

    ranges = [r for r in result]
    pool.putconn(conn)

    print(json.dumps(ranges, indent=2))
    total = sum(r[2] for r in ranges)

    n_ranges = x_parser(ranges)
    # for r in n_ranges:
    #     print(r)

    index_sizes = calc_index_bytes(
        get_table_id(pool, table_name),
        get_index_id(pool, table_name),
        n_ranges
    ) 

    return total, index_sizes




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
    
    # Return index_vector_id as None if it's missing in the key string
    index_vector_id = int(index_raw) if index_raw is not None else None

    return table_id, index_vector_id




def _normalize_key(key: str, fallback_table_id: int | None) -> list[int | None]:
    # 1. Handle Symbolic Start
    if '<TableMin>' in key:
        return [fallback_table_id, 1]

    # 2. Handle Symbolic End
    if '<TableMax>' in key:
        return [fallback_table_id, None]

    # 3. Extract IDs - index_vector_id will be None if not in string
    table_id, index_vector_id = _extract_table_index(key)

    # 4. Use fallback if the key is a boundary without a Table ID
    if table_id is None:
        table_id = fallback_table_id

    # No more raises. Return what we have for the estimation phase.
    return [table_id, index_vector_id]




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
        index_vector_ids: list[int],
        ranges: list[list] # [ [from_t, from_i], [to_t, to_i], size ]
    ) -> dict[int, int]:

    out = {index_vector_id: 0 for index_vector_id in index_vector_ids}

    for (from_table, from_idx), (to_table, to_idx), size in ranges:
        matched = []
        
        # Treat None in the starting index as 0 (start of table)
        f_idx = from_idx if from_idx is not None else 0

        # Case A: Range is entirely within our table
        if from_table == table_id and to_table == table_id:
            if to_idx is None: # Ends at <TableMax>
                matched = [i for i in index_vector_ids if i >= f_idx]
            else:
                matched = [i for i in index_vector_ids if f_idx <= i <= to_idx]

        # Case B: Range starts in our table but ends in another
        elif from_table == table_id:
            matched = [i for i in index_vector_ids if i >= f_idx]

        # Case C: Range starts in a previous table but ends in ours
        elif to_table == table_id:
            if to_idx is None: # Covers the whole table up to Max
                matched = index_vector_ids
            else:
                matched = [i for i in index_vector_ids if i <= to_idx]

        # Case D: Super-range that completely swallows our table
        elif from_table < table_id < to_table:
            matched = index_vector_ids

        for i in matched:
            out[i] += size

    return out



