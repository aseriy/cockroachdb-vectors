#!/usr/bin/env python3
"""
vectorize_demo_data.py

Instruments and embeds vector columns for demo data tables in CockroachDB.
For each table, adds vector columns for 'name' and 'description' fields and populates embeddings.

Usage:
    python3 vectorize_demo_data.py -u postgresql://... -m hf_st_all_minilm_l6 -s hf
"""

import argparse
import logging
import subprocess
import sys
import os
from math import ceil
from typing import List, Tuple

import psycopg

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BATCH_SIZE = 100

# Path to vectorize.py relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTORIZE_PATH = os.path.join(BASE_DIR, "..", "vectorize.py")

# ── Database operations ──────────────────────────────────────────────────────

def get_tables(conn) -> List[str]:
    """Get list of all tables in schema.table format."""
    sql = """
        SELECT schema_name || '.' || table_name
        FROM [SHOW TABLES]
        ORDER BY schema_name, table_name
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def get_row_count(conn, table: str) -> int:
    """Get row count for a table."""
    sql = f"""
        SELECT count(*)
        FROM {table}
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


# ── Vectorize.py operations ──────────────────────────────────────────────────

def run_instrument(url: str, table: str, input_col: str, output_col: str, model: str):
    """Run vectorize.py instrument to add vector column."""
    cmd = [
        sys.executable,
        VECTORIZE_PATH,
        "instrument",
        "-u", url,
        "-t", table,
        "-i", input_col,
        "-o", output_col,
        "-m", model
    ]

    logger.info(f"  Instrumenting {table}.{input_col} -> {output_col}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Check if column already exists - this is expected on reruns
        if "DuplicateColumn" in result.stderr or "already exists" in result.stderr:
            logger.info(f"  Column {output_col} already exists, skipping instrument")
            return

        logger.error(f"  Instrument failed: {result.stderr}")
        raise RuntimeError(f"vectorize.py instrument failed for {table}.{input_col}")

    logger.info(f"  ✓ Instrumented {output_col}")


def run_embed(url: str, table: str, input_col: str, output_col: str, model: str, num_batches: int):
    """Run vectorize.py embed to populate embeddings."""
    cmd = [
        sys.executable,
        VECTORIZE_PATH,
        "embed",
        "-u", url,
        "-t", table,
        "-i", input_col,
        "-o", output_col,
        "-m", model,
        "-b", str(BATCH_SIZE),
        "-n", str(num_batches)
    ]

    logger.info(f"  Embedding {table}.{input_col} ({num_batches} batches of {BATCH_SIZE})")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"  Embed failed: {result.stderr}")
        raise RuntimeError(f"vectorize.py embed failed for {table}.{input_col}")

    logger.info(f"  ✓ Embedded {output_col}")


# ── Main ─────────────────────────────────────────────────────────────────────

def process_table(conn, url: str, table: str, model: str, vector_suffix: str):
    """Process a single table: instrument and embed name and description columns."""
    logger.info(f"=== Processing {table} ===")

    # Get row count for batch calculation
    row_count = get_row_count(conn, table)
    num_batches = ceil(row_count / BATCH_SIZE)
    logger.info(f"  Rows: {row_count}, Batches: {num_batches}")

    # Process name column
    name_vector_col = f"name_{vector_suffix}"
    run_instrument(url, table, "name", name_vector_col, model)
    run_embed(url, table, "name", name_vector_col, model, num_batches)

    # Process description column
    desc_vector_col = f"description_{vector_suffix}"
    run_instrument(url, table, "description", desc_vector_col, model)
    run_embed(url, table, "description", desc_vector_col, model, num_batches)

    logger.info(f"  ✓ {table} complete")


def main():
    parser = argparse.ArgumentParser(description="Vectorize demo data tables in CockroachDB")
    parser.add_argument("-u", "--url", required=True, help="CockroachDB connection URL")
    parser.add_argument("-m", "--model", required=True, help="Embedding model name")
    parser.add_argument("-s", "--vector-suffix", required=True, help="Suffix for vector column names")
    parser.add_argument("table", nargs='*', help="Table name(s) to process")
    parser.add_argument("--all", action="store_true", help="Process all tables")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    with psycopg.connect(args.url) as conn:
        # Get all tables
        all_tables = get_tables(conn)

        if args.all:
            tables_to_process = all_tables
        elif args.table:
            tables_to_process = args.table
            # Validate that specified tables exist
            for table in tables_to_process:
                if table not in all_tables:
                    logger.error(f"Unknown table '{table}'. Available: {all_tables}")
                    return
        else:
            logger.error("Specify table name(s) or --all")
            return

        logger.info(f"Processing {len(tables_to_process)} tables")

        # Process each table
        for table in tables_to_process:
            try:
                process_table(conn, args.url, table, args.model, args.vector_suffix)
            except Exception as e:
                logger.error(f"Failed to process {table}: {e}")
                logger.info("Continuing with next table...")
                continue

    logger.info("All done.")


if __name__ == "__main__":
    main()
