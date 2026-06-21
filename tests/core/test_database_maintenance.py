"""Tests de utilidades de mantenimiento SQLite."""
from db.config import DatabaseConfig
from db.connection import Database
from db.maintenance import DatabaseMaintenance
from db.migration import ensure_migrations


def test_table_row_counts_and_preview(tmp_path):
    db = Database(DatabaseConfig(path=tmp_path / "test.db"))
    db.connect()
    ensure_migrations(db)
    maintenance = DatabaseMaintenance(db)

    db.execute(
        "INSERT INTO items (name, description) VALUES ('A', 'demo')"
    )

    counts = dict(maintenance.table_row_counts())
    assert counts["items"] >= 1

    columns, rows = maintenance.fetch_table_preview("items", limit=5)
    assert "name" in columns
    assert rows

    result = maintenance.execute_sql("SELECT name FROM items")
    assert result.kind == "select"
    assert result.row_count >= 1

    db.close()
