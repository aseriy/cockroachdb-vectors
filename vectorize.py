import click
import json
from operations import (
    run_embed,
    run_search,
    run_emit,
    run_model_list, run_model_desc,
    run_instrument,
    run_size,
    run_cleanup
)


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



def common_options(f):
    f = click.option("-u", "--url", required=True, help="CockroachDB connection URL")(f)
    f = click.option("-t", "--table", required=True, help="Target table name")(f)
    f = click.option("-i", "--input", "input_col", required=True, help="Column containing input text")(f)
    f = click.option("-o", "--output", "output_col", required=True, help="Column to store the vector")(f)
    f = click.option("-v", "--verbose", is_flag=True, help="Verbose output (used for debugging)")(f)
    return f

def model_options(f):
    f = click.option("-m", "--model", required=True, help="Embedding model. See 'model list' for available models")(f)
    return f



@cli.command(short_help="Vectorize rows in CockroachDB using a specified encoding model.")
@common_options
@model_options
@click.option("-b", "--batch-size", default=1000, type=int, help="Rows to process per batch")
@click.option("-n", "--num-batches", default=1, type=int,
              help="Number of batches to process before exiting (default: 1). 0: keep vectorizing new NULL rows indefinitely")
@click.option("-F", "--follow", is_flag=True,
              help="Keep running: keep vectorizing new NULL rows indefinitely")
@click.option("--min-idle", default=15, type=int,
              help="Initial idle backoff between empty scans, in SECONDS (default: 15)")
@click.option("--max-idle", default=1, type=int,
              help="Max idle time before exit, in MINUTES (default: 1)")
@click.option("-w", "--workers", default=1, type=int,
              help="Number of parallel workders to use (default: 1)")
@click.option("-p", "--progress", is_flag=True, help="Show progress bar")
@click.option("-d", "--dry-run", "dry_run", is_flag=True,
              help="Print SQL statements without executing (only valid with --verbose)")
def embed(
    url,
    table,
    input_col,
    output_col,
    model,
    batch_size,
    num_batches,
    follow,
    min_idle,
    max_idle,
    workers,
    progress,
    dry_run,
    verbose
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
        "model": model,
        "batch_size": batch_size,
        "num_batches": num_batches,
        "follow": follow,
        "min_idle": min_idle,
        "max_idle": max_idle,
        "workers": workers,
        "progress": progress,
        "dry_run": dry_run,
        "verbose": verbose
    }

    if follow:
        args['num_batches'] = None
        args['progress'] = False


    # print(json.dumps(args, indent=2))
    run_embed(args)


@cli.command(short_help="Run similarity search")
@common_options
@model_options
@click.option("-l", "--limit", default=10, type=int, help="Number of the closest matches (default: 10)")
@click.argument("text", required=True)
def search(
        url,
        table,
        input_col,
        output_col,
        limit,
        model,
        verbose,
        text
):

    args = {
        "url": url,
        "table": table,
        "source": input_col,
        "embedding": output_col,
        "limit": limit,
        "model": model,
        "verbose": verbose,
        "text": text
    }

    run_search(args)



@cli.command(short_help="Emit SQL for integrations")
@common_options
@model_options
@click.option("-s", "--sample", type=str, help="Text to search for")
@click.option("-l", "--limit", default=10, type=int, help="Number of the closest matches (default: 10)")
def sql(
        url,
        table,
        input_col,
        output_col,
        model,
        verbose,
        sample,
        limit
):

    args = {
        "url": url,
        "table": table,
        "source": input_col,
        "embedding": output_col,
        "model": model,
        "verbose": verbose,
        "sample": sample,
        "limit": limit
    }

    run_emit(args)



@cli.command(short_help="Instrument for vector search")
@common_options
@model_options
def instrument(
        url,
        table,
        input_col,
        output_col,
        model,
        verbose
):

    args = {
        "url": url,
        "table": table,
        "source": input_col,
        "embedding": output_col,
        "model": model,
        "verbose": verbose
    }

    run_instrument(args)



@cli.command(short_help="Estimate the storage footprint for a vector column")
@common_options
def size(
        url,
        table,
        input_col,
        output_col,
        verbose
):

    args = {
        "url": url,
        "table": table,
        "source": input_col,
        "embedding": output_col,
        "verbose": verbose
    }

    run_size(args)



@cli.command(short_help="Remove instrumentation for a vectorized column")
@common_options
@model_options
def cleanup(
        url,
        table,
        input_col,
        output_col,
        model,
        verbose
):

    args = {
        "url": url,
        "table": table,
        "source": input_col,
        "embedding": output_col,
        "model": model,
        "verbose": verbose
    }

    run_cleanup(args)




@cli.group(short_help="Explore available vector embedding models.")
def model():
    pass


@model.command(short_help="List available vector embedding models.")
def list():
    args = {}
    run_model_list(args)



@model.command(short_help="Describe spefic model.")
@click.argument("model", required=True)
def desc(model: str):
    args = {
        "model": model
    }
    run_model_desc(args)





if __name__ == "__main__":
    cli()
