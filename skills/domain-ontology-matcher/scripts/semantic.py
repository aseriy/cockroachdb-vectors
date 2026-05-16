# /// script
# dependencies = [
#   "click==8.3.1",
#   "psycopg2-binary==2.9.10",
#   "click==8.3.1",
#   "humanize==4.15.0",
#   "Jinja2==3.1.6",
#   "requests==2.32.4",
#   "urllib3==2.5.0",
# ]
# ///

import click
import json
import sys
import os
import re
import statistics
import subprocess
import psycopg2
from urllib.parse import urlparse, parse_qs
from typing import Any

KNOWLEDGE_DATABASE = "domain_knowledge"
RESEARCH_DATABASE = "research"
RESEARCH_TABLE = "public.research"
EMBEDDING_MODEL = "hf_st_all_minilm_l6"

# Path to vectorize.py relative to this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VECTORIZE_PATH = os.path.join(_SCRIPT_DIR, "..", "..", "..", "vectorize.py")


def build_conn_kwargs(db_url) -> dict[str, Any]:
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query) if parsed.query else {}
    ssl_mode = query_params.get("sslmode", ["require"])[0]

    connection_dict = dict(
        dbname=parsed.path[1:],
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 26257,
        sslmode=ssl_mode
    )

    ssl_keys = ["sslrootcert", "sslcert", "sslkey"]
    for key in ssl_keys:
        if key in query_params:
            connection_dict[key] = query_params[key][0]

    return connection_dict


def ensure_database(conn, db_name):
    """Check if database exists and switch to it."""
    with conn.cursor() as cur:
        cur.execute("SELECT database_name FROM [SHOW DATABASES] WHERE database_name = %s", (db_name,))
        result = cur.fetchone()

        if not result:
            raise click.ClickException(f"Database '{db_name}' does not exist in the cluster")

        cur.execute(f"USE {db_name}")


def get_embedding(text: str, url: str) -> list[float]:
    """Generate embedding vector by calling vectorize.py."""
    cmd = [
        sys.executable,
        VECTORIZE_PATH,
        "input",
        "-u", url,
        "-m", EMBEDDING_MODEL,
        text
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise click.ClickException(f"vectorize.py failed: {result.stderr}")

    return json.loads(result.stdout.strip())


@click.group()
def cli():
    pass


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
def domains(url):
    """List all knowledge domains"""
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        ensure_database(conn, KNOWLEDGE_DATABASE)

        query = """
            SELECT DISTINCT schema_name
            FROM [SHOW TABLES]
            ORDER BY schema_name
        """

        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchall()

        domains_list = [row[0] for row in result]
        print(json.dumps(domains_list, indent=2))

    finally:
        conn.close()


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.argument("domain_name")
@click.argument("ontology", required=False)
def domain(url, domain_name, ontology):
    """List ontologies in a domain, or terms in a specific ontology"""
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        ensure_database(conn, KNOWLEDGE_DATABASE)

        if ontology is None:
            query = """
                SELECT table_name
                FROM [SHOW TABLES]
                WHERE schema_name = %s
                ORDER BY table_name
            """
            with conn.cursor() as cur:
                cur.execute(query, (domain_name,))
                result = cur.fetchall()

            ontologies_list = [row[0] for row in result]
            print(json.dumps(ontologies_list, indent=2))
        else:
            table_name = f"{domain_name}.{ontology}"
            query = f"""
                SELECT name, description
                FROM {table_name}
                ORDER BY name
            """
            with conn.cursor() as cur:
                cur.execute(query)
                result = cur.fetchall()

            terms_list = [{"name": row[0], "description": row[1]} for row in result]
            print(json.dumps(terms_list, indent=2))

    finally:
        conn.close()


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.option("-s", "--vector-suffix", required=True, help="Vector column suffix (e.g., 'hf')")
@click.option("-n", "--top-n", type=int, default=None, help="Number of top results (default: all below median)")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose progress logging")
@click.argument('research_id')
def match(url, vector_suffix, top_n, verbose, research_id):
    """Match against knowledge domain ontologies using research ID (UUID) or text input."""
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        # Detect if input is UUID
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        is_uuid = re.match(uuid_pattern, research_id, re.IGNORECASE)

        if is_uuid:
            # Load research vector from database
            ensure_database(conn, RESEARCH_DATABASE)

            vector_column = f"info_{vector_suffix}"
            query = f"SELECT {vector_column} FROM {RESEARCH_TABLE} WHERE id = %s"

            with conn.cursor() as cur:
                cur.execute(query, (research_id,))
                result = cur.fetchone()

            if not result or not result[0]:
                raise click.ClickException(f"Research ID '{research_id}' not found or has no {vector_column} vector")

            vector = json.loads(result[0])
        else:
            # Vectorize the input text
            vector = get_embedding(research_id, url)

        dimension = len(vector)

        if verbose:
            if is_uuid:
                print(f"Loaded research vector from database (dimension={dimension})", file=sys.stderr)
            else:
                print(f"Vectorized input text (dimension={dimension})", file=sys.stderr)

        # Get all ontology tables
        ensure_database(conn, KNOWLEDGE_DATABASE)

        query = """
            SELECT schema_name || '.' || table_name
            FROM [SHOW TABLES]
            ORDER BY schema_name, table_name
        """

        with conn.cursor() as cur:
            cur.execute(query)
            tables = [row[0] for row in cur.fetchall()]

        if verbose:
            print(f"Found {len(tables)} ontology tables", file=sys.stderr)

        # Calculate median distance for each table
        results = []

        for table in tables:
            desc_vector_col = f"description_{vector_suffix}"

            query = f"""
                SELECT id, name, {desc_vector_col} <=> %s::VECTOR({dimension}) AS distance
                FROM {table}
                WHERE {desc_vector_col} IS NOT NULL
            """

            with conn.cursor() as cur:
                cur.execute(query, (vector,))
                rows = cur.fetchall()

            if verbose and rows:
                print(f"\n{table}:", file=sys.stderr)
                for row in rows:
                    print(f"  {row[0]} | {row[2]:8.4f} | {row[1]}", file=sys.stderr)

            distances = [row[2] for row in rows]

            if distances:
                median_dist = statistics.median(distances)
                results.append((table, median_dist))

                if verbose:
                    print(f"  {table}: median={median_dist:.4f}", file=sys.stderr)

        # Calculate median of all table medians
        if not results:
            table_names = []
        else:
            all_medians = [dist for _, dist in results]
            median_of_medians = statistics.median(all_medians)

            if verbose:
                print(f"\nOverall median of medians: {median_of_medians:.4f}", file=sys.stderr)

            # Keep lower half: tables with median < overall median
            lower_half = [(table, dist) for table, dist in results if dist < median_of_medians]
            lower_half.sort(key=lambda x: x[1])

            if verbose:
                print(f"Lower half contains {len(lower_half)} tables", file=sys.stderr)

            # Apply top-n limit if specified
            if top_n is None:
                top_results = lower_half
            else:
                top_results = lower_half[:top_n]

            table_names = [table for table, _ in top_results]

            if verbose:
                print(f"Returning {len(table_names)} results", file=sys.stderr)

        print(json.dumps(table_names, indent=2))

    except psycopg2.Error as e:
        raise click.ClickException(f"Database error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    cli()
