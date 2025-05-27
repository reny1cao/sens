"""Command to build pre-computed schema indexes."""

import asyncio
from pathlib import Path

import click
import structlog

from sens.schema.graph import SchemaGraph
from sens.schema.precomputed_index import PrecomputedSchemaIndex
from sens.settings import get_settings

log = structlog.get_logger()


@click.command()
@click.option(
    "--schema-path",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    help="Path to schema JSON file",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Force rebuild even if cache exists",
)
def build_schema_index(schema_path: Path, force: bool):
    """Build pre-computed schema indexes for optimized retrieval.

    This command pre-computes various schema relationships and metadata
    to optimize runtime schema retrieval performance.
    """
    settings = get_settings()

    # Use provided schema path or default from settings
    if schema_path:
        schema_file = schema_path
    else:
        schema_file = Path(settings.schema_path)

    if not schema_file.exists():
        click.echo(f"Error: Schema file not found: {schema_file}", err=True)
        raise click.Exit(1)

    click.echo(f"Building pre-computed indexes from: {schema_file}")

    try:
        # Initialize schema graph
        schema_graph = SchemaGraph.get_instance(str(schema_file))

        # Clear cache if force flag is set
        if force:
            cache_dir = Path.home() / ".sens" / "schema_cache"
            cache_file = cache_dir / "precomputed_index.pkl"
            if cache_file.exists():
                cache_file.unlink()
                click.echo("Cleared existing cache")

        # Build pre-computed indexes
        index = PrecomputedSchemaIndex(schema_graph)

        # Display statistics
        click.echo("\nIndex Statistics:")
        click.echo(f"- Tables indexed: {len(index.table_indexes)}")
        click.echo(
            f"- Relationships indexed: {len(index.relationship_index.foreign_keys)}"
        )
        click.echo(f"- Join graph entries: {len(index.relationship_index.join_graph)}")

        # Show sample of indexed tables
        click.echo("\nIndexed Tables:")
        for i, (table_name, table_index) in enumerate(index.table_indexes.items()):
            if i >= 5:  # Show first 5 tables
                click.echo(f"  ... and {len(index.table_indexes) - 5} more")
                break
            click.echo(f"  - {table_name}:")
            click.echo(f"    • Columns: {len(table_index.columns)}")
            click.echo(
                f"    • Primary Keys: {', '.join(table_index.primary_keys) or 'None'}"
            )
            click.echo(
                f"    • Sticky Columns: {', '.join(table_index.sticky_columns) or 'None'}"
            )
            click.echo(f"    • Foreign Keys: {len(table_index.foreign_key_columns)}")

        click.echo("\nPre-computed indexes built successfully!")

    except Exception as e:
        click.echo(f"Error building indexes: {str(e)}", err=True)
        log.exception("Failed to build pre-computed indexes")
        raise click.Exit(1)


if __name__ == "__main__":
    build_schema_index()
