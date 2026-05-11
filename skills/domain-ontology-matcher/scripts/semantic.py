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
import psycopg2
from urllib.parse import urlparse, parse_qs
from typing import Any

DATABASE = "domain_knowledge"


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
def domains(url):
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        ensure_database(conn, DATABASE)

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
    conn = psycopg2.connect(**build_conn_kwargs(url))
    conn.autocommit = True

    try:
        ensure_database(conn, DATABASE)

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


if __name__ == "__main__":
    cli()
