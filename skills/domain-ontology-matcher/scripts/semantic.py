import click
import atexit
import json
from psycopg2.pool import SimpleConnectionPool
from urllib.parse import urlparse, parse_qs
from typing import Any


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


def main_get_conn(pool):
    conn = pool.getconn()
    conn.autocommit = True
    return conn


@click.group()
@click.option("-u", "--url", required=True, help="CockroachDB connection URL")
@click.pass_context
def cli(ctx, url):
    ctx.ensure_object(dict)
    ctx.obj['url'] = url


@cli.command()
@click.pass_context
def domains(ctx):
    url = ctx.obj['url']
    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(url))
    atexit.register(conn_pool.closeall)

    query = """
        SELECT DISTINCT schema_name
        FROM [SHOW TABLES]
        ORDER BY schema_name
    """

    conn = main_get_conn(conn_pool)
    with conn.cursor() as cur:
        cur.execute(query)
        result = cur.fetchall()

    domains_list = [row[0] for row in result]
    print(json.dumps(domains_list, indent=2))

    conn_pool.putconn(conn)


@cli.command()
@click.argument("domain_name")
@click.argument("ontology", required=False)
@click.pass_context
def domain(ctx, domain_name, ontology):
    url = ctx.obj['url']
    conn_pool = SimpleConnectionPool(minconn=1, maxconn=2, **build_conn_kwargs(url))
    atexit.register(conn_pool.closeall)

    conn = main_get_conn(conn_pool)

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

    conn_pool.putconn(conn)


if __name__ == "__main__":
    cli()
