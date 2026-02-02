import os
import sys
import gzip
import json
import time
import random
import argparse
import logging
from tqdm import tqdm
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import execute_values
from urllib.parse import urlparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from datetime import datetime
import importlib
model = importlib.import_module("models.sentence_transformer")

from models.sentence_transformer import embedding_dim, embedding_encode


_WORKER_POOL = None

def main_get_conn(pool):
    conn = pool.getconn()
    conn.autocommit = True
    return conn


def worker_init(db_url):
    global _WORKER_POOL
    if _WORKER_POOL is None:
        _WORKER_POOL = SimpleConnectionPool(
            minconn=1,
            maxconn=2,
            **build_conn_kwargs(db_url)
        )


def worker_get_conn(db_url):
    global _WORKER_POOL
    conn = _WORKER_POOL.getconn()
    conn.autocommit = True
    return conn


def worker_put_conn(conn):
    global _WORKER_POOL
    _WORKER_POOL.putconn(conn)


def build_conn_kwargs(db_url):
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


def estimate_total_lines(path):
    count = 0
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for _ in f:
                count += 1
    except Exception:
        return None
    return count

def ensure_vector_column(pool, table_name, output_column, dry_run, show_info=True):
    conn = main_get_conn(pool)

    existing = None
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT a.attname, t.typname
            FROM pg_attribute a
            JOIN pg_type t ON a.atttypid = t.oid
            WHERE a.attrelid = %s::regclass
              AND a.attname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
        """, (table_name, output_column))
        existing = cur.fetchone()

    pool.putconn(conn)

    if existing:
        if 'vector' not in existing[1]:
            raise RuntimeError(f"Column {output_column} exists but is not of VECTOR type.")
        if show_info:
            print(f"[INFO] Column {output_column} already exists")
        return

    conn = pool.getconn()

    with conn.cursor() as cur:
        vector_dim = model.embedding_dim()
        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{output_column}" VECTOR({vector_dim})'
        if dry_run:
            print(f"[DRY RUN] Would execute: {sql}")
        else:
            cur.execute(sql)

    pool.putconn(conn)



def get_primary_key_column(pool, table_name):
    conn = main_get_conn(pool)

    pk_result = None

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT a.attname
            FROM   pg_index i
            JOIN   pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE  i.indrelid = %s::regclass AND i.indisprimary
        """, (table_name,))
        pk_result = cur.fetchone()

    pool.putconn(conn)

    if not pk_result:
        raise RuntimeError(f"No primary key found for table '{table_name}'")

    return pk_result[0]

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
                cur.execute(f'SELECT "{primary_key}" FROM "{table_name}" WHERE "{output_column}" IS NULL LIMIT %s', (limit,))
                ids = [row[0] for row in cur.fetchall()]

            pool.putconn(conn)

        except Exception as e:
            if attempt < max_retries:
                print(f"[WARN] Retry {attempt}/{max_retries} on fetch_null_vector_ids: {e}", flush=True)
                time.sleep(0.5 * attempt + random.uniform(0, 0.3))
            else:
                raise

    return ids



# Vectorizes a batch of rows by primary key.
# - Establishes a new DB connection per batch.
# - Encodes using SentenceTransformer in parallel.
# - Retries on failure with exponential backoff.
# - Reports status to tqdm or stdout depending on mode.

def vectorize_batch(
                    db_url, table_name,
                    input_column, output_column, primary_key, ids,
                    dry_run, verbose, batch_index=0
                    ):
    
    if not ids:
        return 0

    warnings = []
    errors = []

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

    if not batch:
        worker_put_conn(conn)
        return 0

    values = model.embedding_encode(batch_index, batch, verbose)
    
    #TODO: move to the model modle
    # texts = [row_text for _, row_text in batch]
    # row_ids = [row_id for row_id, _ in batch]
    # model = get_model()
    # embeddings = model.encode(texts, batch_size=128, show_progress_bar=False)

    # if verbose:
    #     for i, (row_id, row_text) in enumerate(zip(row_ids, texts), 1):
    #         input_column_text = row_text[:40].replace('\n', '').replace('\r', '')
    #         print(f"[INFO] (batch {batch_index}, {i}/{len(batch)}) Updating vector for row id {row_id}: '{input_column_text}'")

    # values = [(row_id, embedding.tolist()) for row_id, embedding in zip(row_ids, embeddings)]
    # TODO: end


    if not dry_run:
        max_retries = 10
        for attempt in range(1, max_retries + 1):
            try:
                with conn.cursor() as cur:
                    sql = f'''
                        UPDATE "{table_name}" AS t
                        SET "{output_column}" = v.embedding
                        FROM (VALUES %s) AS v("{primary_key}", embedding)
                        WHERE t."{primary_key}"::STRING = v."{primary_key}"
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

    worker_put_conn(conn)
    return len(batch), errors, warnings



def main():
    parser = argparse.ArgumentParser(description="Vectorize rows in CockroachDB using SentenceTransformers.")
    parser.add_argument("-u", "--url", required=True, help="CockroachDB connection URL")
    parser.add_argument("-t", "--table", required=True, help="Target table name")
    parser.add_argument("-i", "--input", required=True, help="Column containing input text")
    parser.add_argument("-o", "--output", required=True, help="Column to store the vector")
    parser.add_argument("-b", "--batch-size", type=int, default=1000, help="Rows to process per batch")
    parser.add_argument("-n", "--num-batches", type=int, default=1,
                        help="Number of batches to process before exiting (default: 1)")
    parser.add_argument("-F", "--follow", action="store_true",
                        help="Keep running: keep vectorizing new NULL rows indefinitely")
    parser.add_argument("--max-idle", type=float, default=60.0,
                        help="Max idle time before exit, in MINUTES (0 = no idle limit)")
    parser.add_argument("--min-idle", type=float, default=15.0,
                        help="Initial idle backoff between empty scans, in SECONDS")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Number of parallel workders to use (default: 1)")

    # Disallow verbose and progress together
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("-v", "--verbose", action="store_true", help="Verbose output (used for debugging)")
    group1.add_argument("-p", "--progress", action="store_true", help="Show progress bar")

    parser.add_argument("-d", "--dry-run", action="store_true", help="Print SQL statements without executing (only valid with --verbose)")
    args = parser.parse_args()

    if args.dry_run:
        args.workers = 1
        args.verbose = True
        args.progress = False

    executor = ProcessPoolExecutor(
        max_workers=min(args.workers, multiprocessing.cpu_count()),
        initializer=worker_init, initargs=(args.url,)
    )
    
    conn_pool = SimpleConnectionPool(minconn=0, maxconn=5, **build_conn_kwargs(args.url))


    batch_counter = 0

    primary_key = get_primary_key_column(conn_pool, args.table)
    ensure_vector_column(
        conn_pool,
        args.table,
        args.output,
        args.dry_run,
        show_info=not args.progress
    )

    pbar = None

    futures = []
    warnings = []
    errors = []

    # Backoff state
    idle_wait = max(0.001, float(args.min_idle))   # seconds
    idle_spent = 0.0                               # seconds
    idle_budget = max(0.0, float(args.max_idle) * 60.0)  # seconds (0 = unlimited)

    start = time.time() if args.verbose else None

    # Per-run counters (1-based for human-friendly logs)
    run_counter = 1
    batch_in_run = 1

    while True:
        # Stop after N batches per run (default 1) unless following
        if (not args.follow) and batch_in_run > args.num_batches:
            break

        if args.progress and batch_in_run == 1:
            total_rows = args.batch_size * args.num_batches
            if args.follow:
                total_rows = get_null_vector_row_count(conn_pool, args.table, args.output, primary_key)

            pbar = tqdm(
                        total=total_rows,
                        desc="Vectorizing",
                        unit="rows",
                        smoothing=0.01
                    )

            def _on_done(fut):
                try:
                    processed, _, _ = fut.result()
                except Exception:
                    return
                if processed:
                    pbar.update(processed)


        # Fetch one page of IDs (no wait on start or after successful work)
        ids = fetch_null_vector_ids(conn_pool, args.table, args.output, primary_key, args.batch_size)

        chunk_size = int(0.5 + len(ids) / args.workers)
        futures = []

        # Run one batch (via pool for per-process model reuse)
        if args.verbose:
            print(f"[INFO] Run {run_counter}, Batch {batch_in_run} starting ({len(ids)} rows)")

        for i in range(0, len(ids), chunk_size):
            id_chunk = ids[i : i + chunk_size]

            # Got work → reset backoff
            idle_wait = max(0.001, float(args.min_idle))
            idle_spent = 0.0

            fut = executor.submit(
                vectorize_batch,
                args.url, args.table,
                args.input, args.output, primary_key, id_chunk,
                args.dry_run, args.verbose, batch_in_run
            )
            if args.progress:
                fut.add_done_callback(_on_done)
            
            futures.append(fut)
            
        for fut in as_completed(futures):
            worker_count, worker_errors, worker_warnings = fut.result()
            errors.extend(worker_errors)
            warnings.extend(worker_warnings)

        batch_counter += 1
        batch_in_run += 1
        if args.follow and batch_in_run > args.num_batches:
            if args.verbose:
                print(f"[INFO] Run {run_counter} complete ({args.num_batches} batches).")

            if args.progress and pbar is not None:
                pbar.close()
                pbar = None

            run_counter += 1
            batch_in_run = 1

        continue

        # No work returned → back off or exit if max idle reached
        if idle_budget > 0.0 and idle_spent >= idle_budget:
            if args.verbose:
                print(f"[INFO] Max idle reached ({args.max_idle} min). Exiting.")
            break

        # Sleep current backoff and then double it (exponential), cap by remaining budget if any
        to_sleep = idle_wait
        if idle_budget > 0.0:
            remaining = max(0.0, idle_budget - idle_spent)
            to_sleep = min(to_sleep, remaining)
        time.sleep(to_sleep)
        idle_spent += to_sleep
        idle_wait = idle_wait * 2.0

    if args.verbose:
        print("Done in", time.time() - start, "seconds")




    if args.verbose:
        print("[INFO] Vectorization complete.")

    if args.progress and (warnings or errors):
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


if __name__ == "__main__":
    main()
