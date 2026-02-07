import click
import json
from operations import run_encode


class OperationGroup(click.Group):
    def format_commands(self, ctx, formatter):
        # This overrides the 'Commands' header
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            commands.append((subcommand, cmd.get_short_help_str()))

        if commands:
            with formatter.section("Operations"):
                formatter.write_dl(commands)



@click.group(
    cls=OperationGroup,
    options_metavar="[OPTIONS]",
    subcommand_metavar="OPERATION [ARGS]..."
)
def cli():
    pass



def shared_db_options(f):
    f = click.option("-u", "--url", required=True, help="CockroachDB connection URL")(f)
    f = click.option("-t", "--table", required=True, help="Target table name")(f)
    f = click.option("-v", "--verbose", is_flag=True, help="Verbose output (used for debugging)")(f)
    return f



@cli.command(help="Vectorize rows in CockroachDB using SentenceTransformers.")
@shared_db_options
@click.option("-i", "--input", "input_col", required=True, help="Column containing input text")
@click.option("-o", "--output", "output_col", required=True, help="Column to store the vector")
@click.option("-b", "--batch-size", default=1000, type=int, help="Rows to process per batch")
@click.option("-n", "--num-batches", default=1, type=int,
              help="Number of batches to process before exiting (default: 1)")
@click.option("-F", "--follow", is_flag=True,
              help="Keep running: keep vectorizing new NULL rows indefinitely")
@click.option("--max-idle", default=60.0, type=float,
              help="Max idle time before exit, in MINUTES (0 = no idle limit)")
@click.option("--min-idle", default=15.0, type=float,
              help="Initial idle backoff between empty scans, in SECONDS")
@click.option("-w", "--workers", default=1, type=int,
              help="Number of parallel workders to use (default: 1)")
@click.option("-p", "--progress", is_flag=True, help="Show progress bar")
@click.option("-d", "--dry-run", "dry_run", is_flag=True,
              help="Print SQL statements without executing (only valid with --verbose)")
def encode(
    url,
    table,
    verbose,
    input_col,
    output_col,
    batch_size,
    num_batches,
    follow,
    max_idle,
    min_idle,
    workers,
    progress,
    dry_run,
):

    if verbose and progress:
        raise click.UsageError("--verbose and --progress are mutually exclusive")

    if dry_run:
        workers = 1
        verbose = True
        progress = False

    args = {
        "url": url,
        "table": table,
        "input": input_col,
        "output": output_col,
        "batch_size": batch_size,
        "num_batches": num_batches,
        "follow": follow,
        "max_idle": max_idle,
        "min_idle": min_idle,
        "workers": workers,
        "verbose": verbose,
        "progress": progress,
        "dry_run": dry_run,
    }

    print(json.dumps(args, indent=2))
    run_encode(args)


@cli.command()
@shared_db_options
def search(url, table, verbose):
    pass


@cli.command()
def model():
    pass


if __name__ == "__main__":
    cli()
