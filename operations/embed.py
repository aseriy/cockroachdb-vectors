import time
import random
from tqdm import tqdm
import atexit
import re
import os, sys
import textwrap
import click
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import execute_values
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from datetime import datetime
import jinja2
import importlib
from .model import is_valid_model
from .common import (
    build_conn_kwargs,
    main_get_conn,
    get_primary_key_column,
    get_column_type
)
from .instrument import is_vector_column


_WORKER_POOL = None
model = None


def worker_init(db_url):
    global _WORKER_POOL
    if _WORKER_POOL is None:
        _WORKER_POOL = SimpleConnectionPool(
            minconn=1,
            maxconn=2,
            **build_conn_kwargs(db_url)
        )
        atexit.register(_WORKER_POOL.closeall)


def worker_get_conn(db_url):
    global _WORKER_POOL
    conn = _WORKER_POOL.getconn()
    conn.autocommit = True
    return conn


def worker_put_conn(conn):
    global _WORKER_POOL
    _WORKER_POOL.putconn(conn)




def get_null_vector_row_count(pool, table_name, output_column, primary_key):
    count = 0
    conn = main_get_conn(pool)
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT("{primary_key}") FROM "{table_name}" WHERE "{output_column}" IS NULL')
        count = cur.fetchone()[0]

    pool.putconn(conn)
    return count


def fetch_null_vector_ids(pool, table_name, output_column, primary_key, limit, verbose=False):
    max_retries = 10
    ids = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = main_get_conn(pool)
            with conn.cursor() as cur:
                cur.execute(f"""
                            SELECT "{primary_key}" FROM "{table_name}"
                            WHERE "{output_column}" IS NULL
                            LIMIT %s
                            """,
                            (limit,))
                ids = [row[0] for row in cur.fetchall()]

            pool.putconn(conn)

        except Exception as e:
            if attempt < max_retries:
                print(f"[WARN] Retry {attempt}/{max_retries} on fetch_null_vector_ids: {e}", flush=True)
                time.sleep(0.5 * attempt + random.uniform(0, 0.3))
            else:
                raise

    return ids



def batch_embed(
                db_url,
                table_name, input_column,
                primary_key, ids,
                dry_run, verbose, batch_index=0
                ):
    
    if not ids:
        return None

    batch = None

    conn = worker_get_conn(db_url)
    with conn.cursor() as cur:
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(
            f'''
                SELECT "{primary_key}", "{input_column}"
                FROM "{table_name}"
                WHERE "{primary_key}" IN ({placeholders})
            ''', ids)
        batch = cur.fetchall()
    
    worker_put_conn(conn)

    if not batch:
        return None

    if verbose:
        for i, (row_id, row_text) in enumerate(batch, 1):
            input_column_text = row_text[:40].replace('\n', '').replace('\r', '')
            print(f"[INFO] (batch {batch_index}, {i}/{len(batch)}) Updating vector {row_id}: '{input_column_text}'")


    values = model.embedding_encode_batch(batch_index, batch, verbose)
    return values
    


def batch_update(
                pool, table_name, output_column,
                primary_key, primary_key_type,
                values,
                dry_run, verbose, batch_index=0
                ):

    warnings = []
    errors = []

    conn = main_get_conn(pool)

    if not dry_run:
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                with conn.cursor() as cur:
                    sql = f'''
                        UPDATE "{table_name}" AS t
                        SET "{output_column}" = v.embedding
                        FROM (VALUES %s) AS v("{primary_key}", embedding)
                        WHERE t."{primary_key}" = v."{primary_key}"::"{primary_key_type}"
                    '''
                    execute_values(cur, sql, values, template="(%s, %s)")
                conn.commit()
                break
            except Exception as e:
                conn.rollback()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if attempt < max_retries:
                    warnings.append(f"[{timestamp}] [WARN] (batch {batch_index}) Retry {attempt}/{max_retries} after failure: {e}")
                    time.sleep(0.5 * attempt + random.uniform(0, 0.3))
                else:
                    errors.append(f"[{timestamp}] [ERROR] Failed after {max_retries} retries: {e}")

    pool.putconn(conn)
    return len(values), errors, warnings



def process_single_batch(
    executor: ProcessPoolExecutor,
    conn_pool: SimpleConnectionPool,
    url: str, table: str,
    primary_key: str, primary_key_type: str,
    source_column: str, vector_column: str,
    ids: list,
    workers: int,
    batch_counter: int,
    verbose: bool = False,
    progress: bool = False,
    dry_run: bool = False
):

    chunk_size = int(0.5 + len(ids) / workers)
    futures = []

    # Run one batch (via pool for per-process model reuse)
    if verbose:
        print(f"[INFO] Batch {batch_counter} starting ({len(ids)} rows)")

    embeddings = []

    for i in range(0, len(ids), chunk_size):
        id_chunk = ids[i : i + chunk_size]

        # # Got work → reset backoff
        # idle_wait = max(0.001, float(args['min_idle']))
        # idle_spent = 0.0

        fut = executor.submit(
            batch_embed,
            url,
            table, source_column,
            primary_key, id_chunk,
            dry_run, verbose, batch_counter
        )

        if progress:
            fut.add_done_callback(_on_done_embed)
        
        futures.append(fut)
        
    for fut in as_completed(futures):
        embeddings.extend(fut.result())

    update_count, worker_errors, worker_warnings = batch_update(
        conn_pool, table, vector_column,
        primary_key, primary_key_type,
        embeddings,
        dry_run, verbose, batch_counter
    )

    return  update_count, worker_errors, worker_warnings


# This is called when --follow option is in effect
def run_embed_follow(
    executor: ProcessPoolExecutor,
    conn_pool: SimpleConnectionPool,
    url: str, table: str,
    primary_key: str, primary_key_type: str,
    source_column: str, vector_column: str,
    batch_size,
    workers: int,
    min_idle: int, max_idle: int,
    verbose: bool = False
):
    # Backoff state
    idle_wait = 0
    max_idle_secs = max_idle *  60
    to_sleep = 1
    
    batch_counter = 1
        
    while True:
        # Fetch one batchfull of IDs (no wait on start or after successful work)
        ids = fetch_null_vector_ids(conn_pool, table, vector_column, primary_key, batch_size)

        if ids:
            # Got work!!! Reset the current idle_time
            idle_wait = 0
            to_sleep = 1

            update_count, worker_errors, worker_warnings = process_single_batch(
                executor,
                conn_pool,
                url, table,
                primary_key, primary_key_type,
                source_column, vector_column,
                ids,
                workers,
                batch_counter,
                verbose,
                False,
                False
            )

            # Increment counters
            batch_counter += 1

        else:
            if verbose:
                print(f"[INFO] idle_wait: {idle_wait}")

            # No work returned
            if idle_wait >= max_idle_secs:
                if verbose:
                    print(f"[INFO] Max idle reached ({max_idle} minutes). Exiting.")
                
                break

            else:
                if verbose:
                    msg = 'No work found.'
                    if idle_wait > 0:
                        msg = f"No work for {idle_wait} secs."

                    print(f"[INFO] {msg} Sleeping for {to_sleep} secs...")

                time.sleep(to_sleep)
                idle_wait += to_sleep
                to_sleep *= 2




    

def run_embed_n_batches(
    executor: ProcessPoolExecutor,
    conn_pool: SimpleConnectionPool,
    url: str, table: str,
    primary_key: str, primary_key_type: str,
    source_column: str, vector_column: str,
    batch_size, num_batches,
    workers: int,
    verbose: bool = False,
    progress: bool = False,
    dry_run: bool = False
):
    pbar = None

    # Set up the progress bar
    if progress:
        total_rows = batch_size * num_batches

        pbar = tqdm(
                    total=total_rows,
                    desc="Vectorizing",
                    unit="rows",
                    smoothing=0.01
                )

        def _on_done_embed(fut):
            try:
                embeddings = fut.result()
            except Exception:
                return
            if embeddings:
                pbar.update(len(embeddings))


    warnings = []
    errors = []

    start = time.time() if verbose else None

    for batch in range(1, num_batches+1):
        # Fetch one batchfull of IDs (no wait on start or after successful work)
        ids = fetch_null_vector_ids(conn_pool, table, vector_column, primary_key, batch_size)

        if not ids:
            if verbose:
                print(f"[INFO] No work found. Exiting... ")
            break


        if ids:
            update_count, worker_errors, worker_warnings = process_single_batch(
                executor,
                conn_pool,
                url, table,
                primary_key, primary_key_type,
                source_column, vector_column,
                ids,
                workers,
                batch,
                verbose,
                progress,
                dry_run
            )
            
            errors.extend(worker_errors)
            warnings.extend(worker_warnings)

    # end for


    print("Done in", time.time() - start, "seconds")
    if verbose and ids:
        print("[INFO] Embedding complete.")

    if (progress or verbose) and (warnings or errors):
        from datetime import datetime
        print("\n[WARNINGS SUMMARY]", flush=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"warnings_{timestamp}.log"
        with open(log_filename, "w") as f:
            for w in warnings:
                print(w)
                f.write(w + "\n")
        print(f"Total warnings: {len(warnings)}")
        print("\n[ERROR SUMMARY]", flush=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"errors_{timestamp}.log"
        with open(log_filename, "w") as f:
            for w in errors:
                print(w)
                f.write(w + "\n")
        print(f"Total errors: {len(errors)}")






def run_embed(args):
    if not is_valid_model(args['model']):
        raise RuntimeError(f"Invalid embedding model {args['model']}")

    global model
    model = importlib.import_module(f"models.{args['model']}")

    executor = ProcessPoolExecutor(
        max_workers=min(args['workers'], multiprocessing.cpu_count()),
        initializer=worker_init, initargs=(args['url'],)
    )
    
    conn_pool = SimpleConnectionPool(minconn=0, maxconn=args['workers'], **build_conn_kwargs(args['url']))
    atexit.register(conn_pool.closeall)

    primary_key, primary_key_type = get_primary_key_column(conn_pool, args['table'])

    # Check if the specified vector column exist.
    # If it doesn't, recommend running "instrument"
    if not is_vector_column(
                    conn_pool,
                    args['table'], args['output'],
                    model.embedding_dim(),
                    not args['progress']
            ):
        ctx = click.get_current_context()
        msg = f"""
            Column {args['output']} doesn't exist.

            Run:
            {os.path.basename(sys.executable)} {ctx.find_root().info_name} instrument ...

            to create the vector column.
        """
        print(textwrap.dedent(msg))
        return



    # Call the correct mode depending on batch run or daemon
    if args['follow']:
        run_embed_follow(
            executor,
            conn_pool,
            args['url'], args['table'],
            primary_key, primary_key_type,
            args['input'], args['output'],
            args['batch_size'],
            args['workers'],
            args['min_idle'], args['max_idle'],
            args['verbose']
        )
    
    else:
        run_embed_n_batches(
            executor,
            conn_pool,
            args['url'], args['table'],
            primary_key, primary_key_type,
            args['input'], args['output'],
            args['batch_size'], args['num_batches'],
            args['workers'],
            args['verbose'],
            args['progress'],
            args['dry_run']
        )




