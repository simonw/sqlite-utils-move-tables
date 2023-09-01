import click
import sqlite_utils


@sqlite_utils.hookimpl
def register_commands(cli):
    @cli.command()
    @click.argument(
        "origin",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, allow_dash=False),
        required=True,
    )
    @click.argument(
        "destination",
        type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
        required=True,
    )
    @click.argument("tables", nargs=-1)
    @click.option(
        "--keep", is_flag=True, help="Don't drop tables from origin after the move"
    )
    @click.option(
        "--ignore", is_flag=True, help="Ignore tables that are missing or already moved"
    )
    @click.option(
        "--replace",
        is_flag=True,
        help="Replace tables in destination if they exist already",
    )
    def move_tables(origin, destination, tables, keep, ignore, replace):
        """
        Move tables from origin database file to destination

        Example usage:

        \b
            sqlite-utils move-tables origin.db destination.db table1 table2

        Copies just the table schema and row data, no foreign key constraints
        or triggers or indexes.
        """
        origin_db = sqlite_utils.Database(origin)
        destination_db = sqlite_utils.Database(destination)

        origin_tables = origin_db.table_names()
        destination_tables = destination_db.table_names()

        # First, validate that everything is OK
        if not ignore:
            for table_name in tables:
                if table_name not in origin_tables:
                    raise click.ClickException(
                        "Table {} is not present in {}".format(table_name, origin)
                    )
                if table_name in destination_tables and not replace:
                    raise click.ClickException(
                        "Table {} already exists in {}".format(table_name, destination)
                    )

        # Now copy across the tables
        for table_name in tables:
            table = origin_db[table_name]
            if not table.exists() and ignore:
                continue
            kwargs = {}
            if not table.use_rowid:
                pks = table.pks
                if len(pks) == 1:
                    kwargs["pk"] = pks[0]
                else:
                    kwargs["pk"] = pks
            destination_db[table_name].create(
                table.columns_dict, **kwargs, replace=replace
            )
            origin_db.attach("destination", destination)
            with origin_db.conn:
                origin_db.execute(
                    "insert into destination.[{table}] select * from [{table}]".format(
                        table=table_name
                    )
                )
                if not keep:
                    table.drop()
