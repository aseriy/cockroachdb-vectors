import click
import json
import sys
import psycopg2
from urllib.parse import urlparse, parse_qs
from typing import Any

DATABASE = "research"


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


@click.group()
def cli():
    pass


@cli.command()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.option('-f', '--file', type=click.Path(exists=True), help='JSON file path')
@click.argument('company_name')
def save(url, file, company_name):
    # Read JSON from file or stdin
    if file:
        with open(file, 'r') as f:
            info_json = json.load(f)
    else:
        info_json = json.load(sys.stdin)

    # Create direct connection
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        ensure_database(conn, DATABASE)

        # Create table if not exists
        create_table_query = """
            CREATE TABLE IF NOT EXISTS public.research (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                at TIMESTAMPTZ DEFAULT now(),
                company TEXT,
                info JSONB
            )
        """

        with conn.cursor() as cur:
            cur.execute(create_table_query)

        # Create GIN index on info column if not exists
        create_index_query = """
            CREATE INDEX IF NOT EXISTS idx_research_info ON public.research USING GIN (info)
        """

        with conn.cursor() as cur:
            cur.execute(create_index_query)

        # Insert the research data
        insert_query = """
            INSERT INTO public.research (company, info)
            VALUES (%s, %s)
            RETURNING id, at
        """

        with conn.cursor() as cur:
            cur.execute(insert_query, (company_name, json.dumps(info_json)))
            result = cur.fetchone()

        print(json.dumps({
            "id": str(result[0]),
            "at": result[1].isoformat(),
            "company": company_name,
            "status": "saved"
        }, indent=2))

    finally:
        conn.close()


if __name__ == "__main__":
    cli()
