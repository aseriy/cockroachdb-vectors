import atexit
import importlib
import json
import re
import humanize
from typing import Any, Sequence, Tuple
from psycopg2.pool import SimpleConnectionPool
from rich.console import Console
from rich.table import Table
from rich.padding import Padding
from rich.align import Align
import statistics
from .model import is_valid_model
from .common import (
    build_conn_kwargs,
    main_get_conn,
    get_table_id,
    get_index_id,
    get_column_type,
    get_primary_key_column
)



def run_size(args: dict):
    verbose = args['verbose']
    schema_name, table_name = args['schema'], args['table']

    if schema_name is not None:
        table_name = f"{schema_name}.{table_name}"

    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    primary_key, primary_key_type = get_primary_key_column(conn_pool, schema_name, table_name) 

    index_vector_name = f"{args['embedding']}_idx"
    index_vector_id = get_index_id(conn_pool, schema_name, table_name, index_vector_name)
    print(f"index_vector_name: {index_vector_name}, index_vector_id: {index_vector_id}")

    index_pk_null_name = f"{args['embedding']}_{primary_key}_null_idx"
    index_pk_null_id = get_index_id(conn_pool, schema_name, table_name, index_pk_null_name)

    index_pk_not_null_name = f"{args['embedding']}_{primary_key}_not_null_idx"
    index_pk_not_null_id = get_index_id(conn_pool, schema_name, table_name, index_pk_not_null_name)

    v_col_type = get_column_type(conn_pool, schema_name, table_name, args['embedding'])
    match = re.match(rf"^vector\((\d+)\)$", v_col_type)
    if not match:
        raise RuntimeError(f"Column {args['embedding']} is {v_col_type} but must be VECTOR().")

    vector_dim = int(match.group(1))

    query = f"""
            SELECT count(*) FROM {table_name}
            """

    row_cnt = 0
    conn = main_get_conn(conn_pool)
    with conn.cursor() as cur:
        cur.execute(query)
        row_cnt = cur.fetchone()[0]
    conn_pool.putconn(conn)

    table_space, index_space, compress_rate = calc_index_space(conn_pool, schema_name, table_name, index_vector_name)
    print(f"table_space: {table_space}, index_space: {json.dumps(index_space, indent=2)}")

    embedding_space = vector_dim * 4 * row_cnt * compress_rate

    # Total extra space including the auxiliary indexes
    vector_space = embedding_space + index_space[index_vector_id]

    # Table space before intrumenting with the toolkit
    init_table_space = table_space - (
            vector_space +
            index_space[index_pk_null_id] +
            index_space[index_pk_not_null_id]
        )

    # Vector space as a percentage of the initial table space
    vector_space_increase_ration = float(vector_space) / float(table_space)

    display_results(
        (
            table_name,                                                  # table name
            humanize.naturalsize(init_table_space, gnu=True),               # init table sapce
            humanize.naturalsize(table_space, gnu=True)                     # resulting table space
        ),
        (
            args['embedding'],                                              # vector column nmae
            humanize.naturalsize(embedding_space, gnu=True),                # actual embedding
            index_vector_name,                                              # vector index name
            humanize.naturalsize(index_space[index_vector_id], gnu=True)    # vector index
        ),
        (
            index_pk_null_name,
            humanize.naturalsize(index_space[index_pk_null_id], gnu=True),
            index_pk_not_null_name,
            humanize.naturalsize(index_space[index_pk_not_null_id], gnu=True)
        ),
        (
            f"{float(vector_space) / float(table_space):.1%}",
            f"{float(index_space[index_pk_null_id] + index_space[index_pk_not_null_id]) / float(table_space):.1%}",
        )
    )
    return



def display_results(
                        table: Tuple[str, str, str],
                        vector: Tuple[str, str, str, str],
                        toolkit: Tuple[str, str, str, str],
                        overhead: Tuple[str, str]
                    ):

    console = Console()

    # 💡 Move padding here (Row Padding, Column Padding)
    report = Table(
                    show_header=False,
                    pad_edge=False,
                    padding=0,
                    show_lines=True
                )

    report.add_column("1") 
    report.add_column("2") 
    report.add_column("3", justify="right") 

    report.add_row(
                    Padding("Initial table size", (0, 4, 0, 1)),
                    Padding(table[0], (0, 4, 0, 1)),
                    Padding(table[1], (0, 0, 0, 6))
                )
    report.add_row(
                    Padding("+ Vector column", (0, 4, 0, 1)),
                    Padding(vector[0], (0, 4, 0, 1)),
                    Padding(vector[1], (0, 0, 0, 6)),
                )
    report.add_row(
                    Padding("+ Vector index", (0, 4, 0, 1)),
                    Padding(vector[2], (0, 4, 0, 1)),
                    Padding(vector[3], (0, 0, 0, 6)),
                )
    report.add_row(
                    Padding("+ Toolkit indexes", (0, 4, 0, 1)),
                    Padding("\n".join([
                                toolkit[0],
                                toolkit[2]
                            ]),
                            (0, 4, 0, 1)),
                    Padding("\n".join([toolkit[1], toolkit[3]]), (0, 0, 0, 6))
                )
    report.add_row(
                    Padding("= Resulting table size", (0, 4, 0, 1)),
                    Padding(table[0], (0, 4, 0, 1)),
                    Padding(table[2], (0, 0, 0, 6))
                )
    report.add_row(
                    Padding(Align(">>>", align="right") , (0, 1, 0, 1)),
                    Padding(Align("Vector storage overhead", align="right"), (0, 1, 0, 1)),
                    Padding(overhead[0], (0, 0, 0, 6))
                )
    report.add_row(
                    Padding(Align(">>>", align="right") , (0, 1, 0, 1)),
                    Padding(Align("Toolkit storage overhead", align="right"), (0, 1, 0, 1)),
                    Padding(overhead[1], (0, 0, 0, 6))
                )

    console.print(report)





def calc_index_space(
                    pool: SimpleConnectionPool,
                    schema_name: str | None,
                    table_name: str,
                    index_vector_name: str,
                ) -> str:

    # index_vector_id = get_index_id(pool, schema_name, table_name, index_vector_name)

    if schema_name is not None:
        table_name = f"{schema_name}.{table_name}"


    # Now pull the list of ranges with disk usage
    query = f"""
        SELECT                                                  
            start_key,
            end_key,
            (span_stats::JSONB ->> 'approximate_disk_bytes')::INT,
            (span_stats::JSONB ->> 'live_bytes')::INT
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

    total = sum(r[2] for r in ranges)

    n_ranges = x_parser(ranges)
    # for r in n_ranges:
    #     print(r)

    index_sizes, compress_rate = calc_index_bytes(
        get_table_id(pool, schema_name, table_name),
        get_index_id(pool, schema_name, table_name),
        n_ranges
    ) 

    return total, index_sizes, compress_rate




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




def x_parser(input: list[list[str, str, int, int]]) -> list[list[list[int | None], list[int | None], int]]:
    out = []

    for from_key, to_key, size_physical, size_logical in input:
        # Pre-extract to get fallback context for symbolic boundaries
        from_table_id, _ = _extract_table_index(from_key)
        to_table_id, _ = _extract_table_index(to_key)

        # Normalize using the other side as a fallback if one side is <TableMin/Max>
        from_boundary = _normalize_key(from_key, fallback_table_id=to_table_id)
        to_boundary = _normalize_key(to_key, fallback_table_id=from_table_id)

        out.append([from_boundary, to_boundary, size_physical, size_logical])

    return out




def calc_index_bytes(
        table_id: int,
        index_vector_ids: list[int],
        ranges: list[list] # [ [from_t, from_i], [to_t, to_i], size ]
    ) -> dict[int, int]:

    print(f"ranges: {json.dumps(ranges, indent=2)}")

    # Compression rate
    compress_rate = [float(r[2]) / r[3] if r[3] > 0 else 1 for r in ranges]
    print(f"compress_rate: {compress_rate}")

    out = {index_vector_id: 0 for index_vector_id in index_vector_ids}

    for (from_table, from_idx), (to_table, to_idx), size_physical, size_logical in ranges:
        matched = []
        
        # Treat None in the starting index as 0 (start of table)
        f_idx = from_idx if from_idx is not None else 0

        # Case A: The entire table is within a single range
        if len(ranges) < 2:
            matched = index_vector_ids

        # Case B: Range is entirely within our table
        elif from_table == table_id and to_table == table_id:
            if to_idx is None: # Ends at <TableMax>
                matched = [i for i in index_vector_ids if i >= f_idx]
            else:
                matched = [i for i in index_vector_ids if f_idx <= i <= to_idx]

        # Case C: Range starts in our table but ends in another
        elif from_table == table_id:
            matched = [i for i in index_vector_ids if i >= f_idx]

        # Case D: Range starts in a previous table but ends in ours
        elif to_table == table_id:
            if to_idx is None: # Covers the whole table up to Max
                matched = index_vector_ids
            else:
                matched = [i for i in index_vector_ids if i <= to_idx]

        # Case E: Super-range that completely swallows our table
        elif from_table < table_id < to_table:
            matched = index_vector_ids

        print(f"matched: {matched}")
        if len(matched) > 0:
            attribution = round(float(size_physical) / len(matched))
            for i in matched:
                out[i] += attribution

    for k,v in out.items():
        print(f"{k}: {v}")

    print(f"compress_rate: {compress_rate}")

    return out, statistics.mean(compress_rate)



