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
from jinja2 import Template
import textwrap

import psycopg
import time
from psycopg.errors import SerializationFailure
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ── Domain definitions ───────────────────────────────────────────────────────

DOMAINS = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "semantic_domains.yaml"), "r") as file:
    DOMAINS = yaml.safe_load(file)

# ── LLM generation ───────────────────────────────────────────────────────────

def generate_batch(client: OpenAI, prompt: str, n: int, model: str) -> List[Dict]:
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
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


def setup_table(conn, schema: str, table: str):
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT NOT NULL,
            description TEXT NOT NULL,
            UNIQUE INDEX name_description_key (name ASC, description ASC)
        )
    """

    with conn.cursor() as cur:
        cur.execute(f"SET search_path = {schema}")
        cur.execute(ddl)
    conn.commit()


def row_count(conn, schema: str, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
        return cur.fetchone()[0]


def insert_rows(conn, schema: str, table: str, rows: List[Dict]) -> int:
    columns = ['name', 'description']

    if not rows:
        return 0
    col_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"""
        INSERT INTO {schema}.{table} (id, {col_str})
        VALUES (gen_random_uuid(), {placeholders})
        ON CONFLICT (name, description) 
        DO NOTHING
    """

    values = []
    for row in rows:
        try:
            values.append(tuple(row[c] for c in columns))
        except KeyError as e:
            logger.warning(f"Skipping row missing key {e}")
    max_retries = 10
    for attempt in range(max_retries):
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, values)
            conn.commit()
            break
        except SerializationFailure:
            conn.rollback()
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * (2 ** attempt))

    return len(values)



    max_retries = 5
    for attempt in range(max_retries):
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, values)
            conn.commit()
            break
        except SerializationFailure:
            conn.rollback()
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * (2 ** attempt))




prompt_tmpl = """
        You are generating a controlled vocabulary, not sample data.

        Task: Produce a list of distinct {{ concept_domain }} concepts.

        Output requirements:

        Return valid JSON only
        Format: an array of objects with exactly two fields: "name" and "description"
        Generate {{ entry_count }} entries
        Each entry must represent a unique {{ concept_unit }} concept (e.g., {{ concept_scope_examples }})
        Do not generate specific instances ({{ instance_exclusion_rules }})
        Avoid synonyms or near-duplicates
        Avoid trivial variants (e.g., {{ trivial_variant_example }})
        Keep names concise (2-5 words)
        Descriptions: 1 sentence, precise and non-overlapping
        Use standard {{ terminology_domain }} terminology

        Quality constraints:

        Concepts must be meaningfully distinct in {{ distinctness_criteria }}
        No repetition or rewording of the same idea
        Stay within realistic {{ domain_name }} domain ({{ domain_scope }})

        Output format example:

        [
            {
                "name": "{{ example_name }}",
                "description": "{{ example_description }}"
            }
        ]

        Now generate the full list.
"""


# ── Main ─────────────────────────────────────────────────────────────────────

def run_domain(conn, client, domain_name, domain_def, target, batch_size, model):
    logger.info(f"=== Domain: {domain_name} ===")
    setup_schema(conn, domain_name)

    for table_name, tdef in domain_def["tables"].items():
        logger.info(f"  Table: {table_name}")
        setup_table(conn, domain_name, table_name)

        current = row_count(conn, domain_name, table_name)
        target = tdef['entry_count']
        logger.info(f"  Existing rows: {current} / {target}")

        # while current < target:
        # n = min(batch_size, target - current)
        n = tdef['entry_count']
        logger.info(f"  Generating {n} rows...")

        template = Template(prompt_tmpl)
        prompt = textwrap.dedent(
            template.render(**tdef)
        )

        rows = generate_batch(client, prompt, n, model)
        if not rows:
            logger.warning("  Empty batch, retrying...")
            continue
        inserted = insert_rows(conn, domain_name, table_name, rows)
        current += inserted
        logger.info(f"  Total: {current} / {target}")

    logger.info(f"  ✓ {table_name} done")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo data for CockroachDB Vector Demo")
    parser.add_argument("-u", "--url", required=True, help="CockroachDB connection URL")
    parser.add_argument("-d", "--domain", help=f"Domain name. Available: {list(DOMAINS.keys())}")
    parser.add_argument("--all", action="store_true", help="Run all domains")
    parser.add_argument("-t", "--target", type=int, default=10000, help="Target rows per table (default: 10000)")
    parser.add_argument("-b", "--batch-size", type=int, default=1000, help="Rows per LLM call (default: 50)")
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
            # print(f"name: {name}")
            # print(f"defn: {json.dumps(defn, indent=2)}")
            run_domain(conn, client, name, defn, args.target, args.batch_size, args.model)

    logger.info("All done.")


if __name__ == "__main__":
    main()
