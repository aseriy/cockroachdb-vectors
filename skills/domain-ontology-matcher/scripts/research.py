# /// script
# dependencies = [
#   "click==8.3.1",
#   "psycopg2-binary==2.9.10",
#   "humanize==4.15.0",
#   "Jinja2==3.1.6",
#   "requests==2.32.4",
#   "urllib3==2.5.0",
#   "tqdm==4.67.1",
#   "rich==15.0.0",
#   "pyyaml"
# ]
# ///

import click
import json
import sys
import os
import re
import psycopg2
from urllib.parse import urlparse, parse_qs
from typing import Any
import subprocess

DATABASE = "research"
EMBEDDING_MODEL = "hf_st_all_minilm_l6"
VECTOR_COLUMN_SUFFIX = "_hf"
SEARCH_LIMIT = 3
DISTANCE_THRESHOLD = 0.5
MAX_RETRY_ATTEMPTS = 5
RETRY_BACKOFF_BASE = 1.0  # seconds

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


def sanitize_and_parse_json(text: str) -> dict:
    """Sanitize and validate JSON input, returning parsed object.

    This prevents JSON parsing errors from invisible control characters
    that may appear in LLM-generated text or web-scraped content.

    Args:
        text: Raw JSON text that may contain control characters

    Returns:
        Parsed JSON object (dict)

    Raises:
        click.ClickException: If JSON is invalid even after sanitization
    """
    # Step 1: Remove problematic Unicode control characters
    problematic_chars = {
        '​',  # ZERO WIDTH SPACE
        '‌',  # ZERO WIDTH NON-JOINER
        '‍',  # ZERO WIDTH JOINER
        '‎',  # LEFT-TO-RIGHT MARK
        '‏',  # RIGHT-TO-LEFT MARK
        '﻿',  # ZERO WIDTH NO-BREAK SPACE (BOM)
    }

    for char in problematic_chars:
        text = text.replace(char, '')

    # Remove other C0 control characters except whitespace
    # JSON allows: tab (0x09), newline (0x0A), carriage return (0x0D)
    cleaned = []
    for char in text:
        code = ord(char)
        if code < 0x20:  # C0 control characters
            if code in (0x09, 0x0A, 0x0D):  # Tab, LF, CR
                cleaned.append(char)
            # Skip other C0 controls
        elif 0x7F <= code < 0xA0:  # DEL and C1 control characters
            # Skip C1 controls
            pass
        else:
            cleaned.append(char)

    sanitized = ''.join(cleaned)

    # Step 2: Validate by parsing
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError as e:
        # Provide context for debugging
        start = max(0, e.pos - 50)
        end = min(len(sanitized), e.pos + 50)
        context = sanitized[start:end]

        raise click.ClickException(
            f"Invalid JSON after sanitization: {e.msg} at line {e.lineno} column {e.colno}\n"
            f"Context: ...{context}...\n"
            f"This is likely a bug in the JSON generation. Please report this error."
        )


def retry_on_operational_error(func, max_attempts=MAX_RETRY_ATTEMPTS):
    """Retry a function on OperationalError with exponential backoff."""
    import time
    import sys

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except psycopg2.OperationalError as e:
            if attempt == max_attempts:
                raise  # Re-raise on final attempt

            wait_time = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            print(f"Connection failed (attempt {attempt}/{max_attempts}): {e}", file=sys.stderr)
            print(f"Retrying in {wait_time:.1f} seconds...", file=sys.stderr)
            time.sleep(wait_time)
        except psycopg2.Error:
            # Non-retryable database error - fail immediately
            raise


def retry_on_vectorize_error(func, max_attempts=MAX_RETRY_ATTEMPTS):
    """Retry a function that calls vectorize.py on subprocess errors with exponential backoff."""
    import time
    import sys

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except click.ClickException as e:
            # Check if this is a vectorize.py failure
            if "vectorize.py failed" not in str(e):
                raise  # Re-raise non-vectorize errors immediately

            if attempt == max_attempts:
                raise  # Re-raise on final attempt

            wait_time = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            print(f"Vectorize service failed (attempt {attempt}/{max_attempts}): {e}", file=sys.stderr)
            print(f"Retrying in {wait_time:.1f} seconds...", file=sys.stderr)
            time.sleep(wait_time)


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


def create_research_table(conn, url):
    """Create research table and index if they don't exist."""

    create_table_query = """
        CREATE TABLE IF NOT EXISTS public.research (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            at TIMESTAMPTZ DEFAULT now(),
            company TEXT NOT NULL,
            domain TEXT NOT NULL,
            info JSONB DEFAULT
        )
    """

    with conn.cursor() as cur:
        cur.execute(create_table_query)

    create_index_query = """
        CREATE INDEX IF NOT EXISTS idx_research_info ON public.research USING GIN (info)
    """

    with conn.cursor() as cur:
        cur.execute(create_index_query)

    # Add vector column and indexes via vectorize.py instrument
    vector_column = f"company{VECTOR_COLUMN_SUFFIX}"

    cmd = [
        sys.executable,
        VECTORIZE_PATH,
        "instrument",
        "-u", url,
        "-t", "research",
        "-i", "company",
        "-o", vector_column,
        "-m", EMBEDDING_MODEL
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise click.ClickException(f"vectorize.py instrument failed: {result.stderr}")


@click.group()
def cli():
    pass


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
def setup(url):
    """Create the research table and index."""
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        ensure_database(conn, DATABASE)
        create_research_table(conn, url)
        print(json.dumps({"status": "research table created"}))

    finally:
        conn.close()


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.option("-d", "--domain", required=True, help="Primary domain name")
@click.option('-f', '--file', type=click.Path(exists=True), help='JSON file path')
@click.argument('company_name')
def save(url, domain, file, company_name):
    # Read JSON from file or stdin
    if file:
        with open(file, 'r') as f:
            info_json = json.load(f)
    else:
        # Read, sanitize, and validate stdin input
        stdin_content = sys.stdin.read()
        info_json = sanitize_and_parse_json(stdin_content)

    conn = None
    try:
        # Encode company name with retry
        company_vector = retry_on_vectorize_error(
            lambda: get_embedding(company_name, url)
        )

        # Encode info JSON as text with retry
        info_text = json.dumps(info_json)
        info_vector = retry_on_vectorize_error(
            lambda: get_embedding(info_text, url)
        )

        def connect_and_save():
            nonlocal conn
            # Create direct connection
            conn = psycopg2.connect(**build_conn_kwargs(url))
            conn.autocommit = True

            ensure_database(conn, DATABASE)
            # Insert the research data
            insert_query = """
                INSERT INTO public.research (company, domain, info, company_hf, info_hf)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, at
            """

            with conn.cursor() as cur:
                cur.execute(insert_query, (
                    company_name,
                    domain,
                    json.dumps(info_json),
                    json.dumps(company_vector),
                    json.dumps(info_vector)
                ))
                return cur.fetchone()

        result = retry_on_operational_error(connect_and_save)

        print(json.dumps({
            "id": str(result[0]),
            "at": result[1].isoformat(),
            "company": company_name,
            "domain": domain,
            "status": "saved"
        }, indent=2))

    except psycopg2.Error as e:
        raise click.ClickException(f"Database error: {e}")
    finally:
        if conn is not None:
            conn.close()


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.option('-d', '--days', type=int, default=90, help='Number of days to look back (default: 90)')
@click.argument('company_name')
def list(url, days, company_name):
    """List research results for a company from the last X days."""
    conn = None
    try:
        conn = psycopg2.connect(**build_conn_kwargs(url))
        conn.autocommit = True

        ensure_database(conn, DATABASE)
        # Get embedding for input company name
        vector = get_embedding(company_name, url)
        dimension = len(vector)

        vector_column = f"company{VECTOR_COLUMN_SUFFIX}"

        query = f"""
            SELECT
                company,
                ARRAY_AGG(json_build_object('id', id, 'at', at) ORDER BY at DESC) AS research,
                {vector_column} <=> %s::VECTOR({dimension}) AS distance
            FROM research
            AS OF SYSTEM TIME follower_read_timestamp()
            WHERE {vector_column} IS NOT NULL
            AND at > now() - interval '%s days'
            GROUP BY company, {vector_column}
            ORDER BY {vector_column} <=> %s::VECTOR({dimension})
            LIMIT %s
        """

        with conn.cursor() as cur:
            cur.execute(query, (vector, days, vector, SEARCH_LIMIT))
            results = cur.fetchall()

        # Filter by distance threshold
        filtered_results = [row for row in results if row[2] < DISTANCE_THRESHOLD]

        output = [
            {
                "company": row[0],
                "research": [
                    {
                        "id": str(r["id"]),
                        "at": r["at"].isoformat() if hasattr(r["at"], 'isoformat') else r["at"]
                    }
                    for r in row[1]
                ]
            }
            for row in filtered_results
        ]

        print(json.dumps(output, indent=2))

    except psycopg2.Error as e:
        raise click.ClickException(f"Database error: {e}")
    finally:
        if conn is not None:
            conn.close()


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.argument('company_name')
def load(url, company_name):
    """Load research by company name (semantic search) or research ID (direct lookup)."""
    conn = None
    try:
        conn = psycopg2.connect(**build_conn_kwargs(url))
        conn.autocommit = True

        ensure_database(conn, DATABASE)

        # Auto-detect if input is UUID
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        is_uuid = re.match(uuid_pattern, company_name, re.IGNORECASE)

        if is_uuid:
            # Load by specific ID
            query = """
                SELECT id, at, company, domain, info
                FROM public.research
                WHERE id = %s
            """

            with conn.cursor() as cur:
                cur.execute(query, (company_name,))
                result = cur.fetchone()

        else:
            # Load by company name using semantic search
            vector = get_embedding(company_name, url)
            dimension = len(vector)
            vector_column = f"company{VECTOR_COLUMN_SUFFIX}"

            # Find closest matching company using vector similarity
            match_query = f"""
                SELECT
                    company,
                    {vector_column} <=> %s::VECTOR({dimension}) AS distance
                FROM research
                WHERE {vector_column} IS NOT NULL
                ORDER BY {vector_column} <=> %s::VECTOR({dimension})
                LIMIT 1
            """

            with conn.cursor() as cur:
                cur.execute(match_query, (vector, vector))
                match_result = cur.fetchone()

            # Check if match is within distance threshold
            if not match_result or match_result[1] >= DISTANCE_THRESHOLD:
                print(json.dumps({}))
                return

            matched_company = match_result[0]

            # Load latest research for the matched company
            load_query = """
                SELECT id, at, company, domain, info
                FROM public.research
                WHERE company = %s
                ORDER BY at DESC
                LIMIT 1
            """

            with conn.cursor() as cur:
                cur.execute(load_query, (matched_company,))
                result = cur.fetchone()

        if result:
            output = {
                "id": str(result[0]),
                "at": result[1].isoformat(),
                "company": result[2],
                "domain": result[3],
                "info": result[4]
            }
            print(json.dumps(output, indent=2))
        else:
            print(json.dumps({}))

    except psycopg2.Error as e:
        raise click.ClickException(f"Database error: {e}")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    cli()
