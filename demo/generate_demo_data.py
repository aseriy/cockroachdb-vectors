#!/usr/bin/env python3
"""
generate_demo_data.py

Generates synthetic domain-specific demo data for the CockroachDB Vector Demo.
Calls an LLM to generate realistic rows and loads them into CockroachDB Serverless.

Usage:
    python3 generate_demo_data.py -u postgresql://... --domain financial_services
    python3 generate_demo_data.py -u postgresql://... --all
    python3 generate_demo_data.py -u postgresql://... --all --target 10000 --batch-size 50
"""

import argparse
import json
import yaml
import logging
import time
import os
from typing import List, Dict

import psycopg
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ── Domain definitions ───────────────────────────────────────────────────────

DOMAINS = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "domains.yaml"), "r") as file:
    DOMAINS = yaml.safe_load(file)

# ── LLM generation ───────────────────────────────────────────────────────────

def generate_batch(client: OpenAI, prompt: str, n: int, model: str) -> List[Dict]:
    filled = prompt.format(n=n)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": filled}],
                temperature=0.9,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            rows = json.loads(content)
            if isinstance(rows, list) and rows:
                return rows
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)
    return []


# ── Database operations ───────────────────────────────────────────────────────

def setup_schema(conn, schema: str):
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    conn.commit()


def setup_table(conn, schema: str, table: str, ddl: str):
    with conn.cursor() as cur:
        cur.execute(f"SET search_path = {schema}")
        cur.execute(ddl)
    conn.commit()


def row_count(conn, schema: str, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
        return cur.fetchone()[0]


def insert_rows(conn, schema: str, table: str, columns: List[str], rows: List[Dict]) -> int:
    if not rows:
        return 0
    col_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {schema}.{table} (id, {col_str}) VALUES (gen_random_uuid(), {placeholders})"
    values = []
    for row in rows:
        try:
            values.append(tuple(row[c] for c in columns))
        except KeyError as e:
            logger.warning(f"Skipping row missing key {e}")
    with conn.cursor() as cur:
        cur.executemany(sql, values)
    conn.commit()
    return len(values)


# ── Main ─────────────────────────────────────────────────────────────────────

def run_domain(conn, client, domain_name, domain_def, target, batch_size, model):
    logger.info(f"=== Domain: {domain_name} ===")
    setup_schema(conn, domain_name)

    for table_name, tdef in domain_def["tables"].items():
        logger.info(f"  Table: {table_name}")
        setup_table(conn, domain_name, table_name, tdef["ddl"])

        current = row_count(conn, domain_name, table_name)
        logger.info(f"  Existing rows: {current} / {target}")

        while current < target:
            n = min(batch_size, target - current)
            logger.info(f"  Generating {n} rows...")
            rows = generate_batch(client, tdef["prompt"], n, model)
            if not rows:
                logger.warning("  Empty batch, retrying...")
                continue
            inserted = insert_rows(conn, domain_name, table_name, tdef["columns"], rows)
            current += inserted
            logger.info(f"  Total: {current} / {target}")

        logger.info(f"  ✓ {table_name} done")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo data for CockroachDB Vector Demo")
    parser.add_argument("-u", "--url", required=True, help="CockroachDB connection URL")
    parser.add_argument("-d", "--domain", help=f"Domain name. Available: {list(DOMAINS.keys())}")
    parser.add_argument("--all", action="store_true", help="Run all domains")
    parser.add_argument("-t", "--target", type=int, default=10000, help="Target rows per table (default: 10000)")
    parser.add_argument("-b", "--batch-size", type=int, default=50, help="Rows per LLM call (default: 50)")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (default: gpt-4o-mini)")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    client = OpenAI(api_key=args.api_key) if args.api_key else OpenAI()

    if args.all:
        to_run = DOMAINS
    elif args.domain:
        if args.domain not in DOMAINS:
            logger.error(f"Unknown domain '{args.domain}'. Available: {list(DOMAINS.keys())}")
            return
        to_run = {args.domain: DOMAINS[args.domain]}
    else:
        logger.error("Specify --domain <name> or --all")
        return

    with psycopg.connect(args.url) as conn:
        for name, defn in to_run.items():
            run_domain(conn, client, name, defn, args.target, args.batch_size, args.model)

    logger.info("All done.")


if __name__ == "__main__":
    main()
