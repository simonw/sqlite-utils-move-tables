from sqlite_utils import Database
from sqlite_utils.cli import cli
from click.testing import CliRunner
import pytest


@pytest.fixture
def databases(tmpdir):
    origin = str(tmpdir / "origin.db")
    origin_db = Database(origin)
    origin_db.vacuum()
    destination = str(tmpdir / "destination.db")
    destination_db = Database(destination)
    destination_db.vacuum()
    return origin, origin_db, destination, destination_db


@pytest.mark.parametrize(
    "extra_args,expected_destination_tables,expected_origin_tables,expected_error",
    (
        ([], {"common"}, {"bar", "common", "foo"}, None),
        (["foo"], {"common", "foo"}, {"bar", "common"}, None),
        (["badtable"], None, None, "Table badtable is not present in"),
        (["badtable", "--ignore"], {"common"}, {"bar", "common", "foo"}, None),
        (["common"], None, None, "Table common already exists in"),
        (["common", "--replace"], {"common"}, {"bar", "foo"}, None),
        (["common", "--replace", "--keep"], {"common"}, {"bar", "common", "foo"}, None),
    ),
)
def test_move_tables_cli(
    databases,
    extra_args,
    expected_destination_tables,
    expected_origin_tables,
    expected_error,
):
    origin, origin_db, destination, destination_db = databases
    origin_db["foo"].insert({"bar": 1})
    origin_db["bar"].insert({"baz": 1})
    origin_db["common"].insert({"bar": 1})
    destination_db["common"].insert({"bar": 1})

    assert destination_db.table_names() == ["common"]

    result = _move_tables(origin, destination, extra_args)
    if expected_error:
        assert result.exit_code != 0
        assert expected_error in result.output
        return

    assert result.exit_code == 0, result.output

    print("=====\n", result.output, "\n=======\n")

    destination_tables = set(destination_db.table_names())
    assert destination_tables == expected_destination_tables

    origin_tables = set(origin_db.table_names())
    assert origin_tables == expected_origin_tables


def test_rowid_only_table(databases):
    origin, origin_db, destination, destination_db = databases

    origin_db["t1"].insert({"name": "Bob"})

    result = _move_tables(origin, destination, ["t1"])
    assert result.exit_code == 0

    assert destination_db.schema == "CREATE TABLE [t1] (\n   [name] TEXT\n);"


def test_single_pk_table(databases):
    origin, origin_db, destination, destination_db = databases

    origin_db["t1"].insert({"id": 4, "name": "Bob"}, pk="id")

    result = _move_tables(origin, destination, ["t1"])
    assert result.exit_code == 0

    assert (
        destination_db.schema
        == "CREATE TABLE [t1] (\n   [id] INTEGER PRIMARY KEY,\n   [name] TEXT\n);"
    )


def test_compound_pk_table(databases):
    origin, origin_db, destination, destination_db = databases

    origin_db["t1"].insert(
        {"category": "person", "id": 4, "name": "Bob"}, pk=("category", "id")
    )

    result = _move_tables(origin, destination, ["t1"])
    assert result.exit_code == 0

    assert destination_db.schema == (
        "CREATE TABLE [t1] (\n"
        "   [category] TEXT,\n"
        "   [id] INTEGER,\n"
        "   [name] TEXT,\n"
        "   PRIMARY KEY ([category], [id])\n"
        ");"
    )


def _move_tables(origin, destination, extra_args=None):
    runner = CliRunner()
    return runner.invoke(
        cli,
        ["move-tables", origin, destination] + (extra_args or []),
        catch_exceptions=False,
    )
