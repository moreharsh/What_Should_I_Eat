"""Databricks SQL parameters must never be interpolated into SQL text."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def load_data_layer():
    redis_module = types.ModuleType("redis")
    redis_module.Redis = types.SimpleNamespace(from_url=lambda *args, **kwargs: MagicMock())
    databricks_module = types.ModuleType("databricks")
    sql_module = types.ModuleType("databricks.sql")
    connection = MagicMock()
    cursor = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    sql_module.connect = MagicMock(return_value=connection)
    databricks_module.sql = sql_module

    spec = importlib.util.spec_from_file_location(
        "tested_data_layer", Path(__file__).resolve().parents[1] / "data_layer.py"
    )
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "redis": redis_module,
        "databricks": databricks_module,
        "databricks.sql": sql_module,
    }
    with patch.dict(sys.modules, stubs), patch.dict(
        "os.environ", {
            "REDIS_URL": "redis://localhost:6379",
            "DATABRICKS_SERVER_HOSTNAME": "test.example",
            "DATABRICKS_HTTP_PATH": "/sql/test",
            "DATABRICKS_PERSONAL_ACCESS_TOKEN": "dummy-token",
        }
    ):
        spec.loader.exec_module(module)
    return module, sql_module.connect, cursor


class DatabricksInsertTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_insert_binds_all_user_fields(self):
        layer, connect, cursor = load_data_layer()
        dish = "Chef's Special'); DROP TABLE default.user_clicks; -- 🍜"
        recipe_json = '{"note":"l’orange 🍜 and \'quote\'"}'
        await layer.log_interaction_to_databricks(
            "user'; --", dish, "Italian's", "Viewed'); --", recipe_json
        )
        self.assertEqual(cursor.execute.call_count, 2)
        ddl = cursor.execute.call_args_list[0].args[0]
        sql_text, parameters = cursor.execute.call_args_list[1].args
        self.assertIn("CREATE TABLE IF NOT EXISTS default.user_clicks", ddl)
        self.assertIn("CURRENT_TIMESTAMP()", sql_text)
        self.assertEqual(sql_text.count("?"), 5)
        for untrusted in ("Chef's", "DROP TABLE", "Italian's", "Viewed');", "user';"):
            self.assertNotIn(untrusted, sql_text)
        self.assertEqual(parameters, (
            "user'; --", dish, "Italian's", "Viewed'); --", recipe_json
        ))
        self.assertEqual(connect.call_count, 1)

    async def test_legacy_insert_uses_bound_lengths(self):
        layer, _, cursor = load_data_layer()
        await layer.log_interaction_to_databricks(
            "u" * 200, "d" * 300, "c" * 200, "t" * 100, "x" * 120_000
        )
        parameters = cursor.execute.call_args_list[-1].args[1]
        self.assertEqual(list(map(len, parameters)), [128, 256, 128, 64, 100_000])

    async def test_insert_failure_does_not_escape_background_task(self):
        layer, _, cursor = load_data_layer()
        cursor.execute.side_effect = RuntimeError("Databricks offline")
        with patch.object(layer.logger, "exception") as log:
            await layer.log_interaction_to_databricks(
                "id", "Pasta", "Italian", "Viewed"
            )
        log.assert_called_once()
        self.assertNotIn("Pasta", log.call_args.args[0])

    async def test_missing_databricks_configuration_skips_writes(self):
        layer, connect, _ = load_data_layer()
        layer.DB_TOKEN = None
        await layer.log_interaction_to_databricks(
            "id", "Pasta", "Italian", "Viewed"
        )
        connect.assert_not_called()

    async def test_profile_events_also_bind_values(self):
        layer, _, cursor = load_data_layer()
        await layer.log_profile_event_to_databricks(
            "id", "O'Brian", "saved", "Chef's Dish", "Italian", ["vegan"]
        )
        sql_text, parameters = cursor.execute.call_args_list[-1].args
        self.assertIn("INSERT INTO default.app_user_events", sql_text)
        self.assertNotIn("Chef's Dish", sql_text)
        self.assertEqual(parameters[0:5], (
            "id", "O'Brian", "saved", "Chef's Dish", "Italian"
        ))


if __name__ == "__main__":
    unittest.main()
