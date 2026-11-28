"""Защита таблицы order_event от UPDATE/DELETE на уровне PostgreSQL (INSERT-ONLY)."""
from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION forbid_order_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Таблица order_event доступна только для добавления (INSERT-ONLY)';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS order_event_insert_only ON order_event;
CREATE TRIGGER order_event_insert_only BEFORE UPDATE OR DELETE ON order_event
    FOR EACH ROW EXECUTE FUNCTION forbid_order_event_mutation();
"""
REVERSE = """
DROP TRIGGER IF EXISTS order_event_insert_only ON order_event;
DROP FUNCTION IF EXISTS forbid_order_event_mutation();
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(SQL, params=None)


def backward(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(REVERSE, params=None)


class Migration(migrations.Migration):
    dependencies = [('orders', '0001_initial')]
    operations = [migrations.RunPython(forward, backward)]
