from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pytest
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType

from devtube_pipeline.warehouse import ensure_table_and_upsert

BASE_ICEBERG_SCHEMA = Schema(
    NestedField(field_id=1, name="video_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="title", field_type=StringType(), required=True),
)
EXTENDED_ICEBERG_SCHEMA = Schema(
    NestedField(field_id=1, name="video_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="title", field_type=StringType(), required=True),
    NestedField(field_id=3, name="s3_uri", field_type=StringType(), required=False),
)


@dataclass
class TestCatalog:
    catalog: Catalog
    namespace: str
    location: str


def arrow_table(s3_uri: str | None) -> pa.Table:
    return pa.table(
        {
            "video_id": ["vid1"],
            "title": ["Some video"],
            "s3_uri": [s3_uri],
        },
        schema=pa.schema(
            [
                pa.field("video_id", pa.string(), nullable=False),
                pa.field("title", pa.string(), nullable=False),
                pa.field("s3_uri", pa.string(), nullable=True),
            ]
        ),
    )


@pytest.fixture()
def test_catalog(tmp_path: Path) -> TestCatalog:
    catalog = load_catalog(f"test-{uuid4().hex}", **{"type": "in-memory"})
    namespace = f"ns_{uuid4().hex[:8]}"
    catalog.create_namespace(namespace)
    return TestCatalog(catalog=catalog, namespace=namespace, location=tmp_path.as_uri())


def upsert(tc: TestCatalog, schema: Schema, table_name: str, table: pa.Table):
    return ensure_table_and_upsert(
        catalog=tc.catalog,
        namespace=tc.namespace,
        table_name=table_name,
        location=f"{tc.location}/{table_name}",
        schema=schema,
        arrow_table=table,
        join_cols=["video_id"],
    )


def load(tc: TestCatalog, table_name: str):
    return tc.catalog.load_table(f"{tc.namespace}.{table_name}")


class TestEnsureTableAndUpsert:
    def test_creates_table_with_full_schema(self, test_catalog) -> None:
        upsert(test_catalog, EXTENDED_ICEBERG_SCHEMA, "fresh", arrow_table("s3://b/k"))

        assert [f.name for f in load(test_catalog, "fresh").schema().fields] == [
            "video_id",
            "title",
            "s3_uri",
        ]

    def test_evolves_existing_table_with_new_column(self, test_catalog) -> None:
        upsert(test_catalog, BASE_ICEBERG_SCHEMA, "legacy", arrow_table(None))

        result = upsert(
            test_catalog, BASE_ICEBERG_SCHEMA, "legacy", arrow_table("s3://b/k")
        )
        assert result.rows_inserted == 0
        assert result.rows_updated == 1

        table = load(test_catalog, "legacy")
        assert "s3_uri" in [f.name for f in table.schema().fields]
        rows = table.scan().to_arrow().to_pylist()
        assert rows[0]["s3_uri"] == "s3://b/k"

    def test_evolution_is_idempotent(self, test_catalog) -> None:
        upsert(test_catalog, EXTENDED_ICEBERG_SCHEMA, "stable", arrow_table("s3://b/k"))
        upsert(test_catalog, EXTENDED_ICEBERG_SCHEMA, "stable", arrow_table("s3://b/k2"))

        rows = load(test_catalog, "stable").scan().to_arrow().to_pylist()
        assert len(rows) == 1
        assert rows[0]["s3_uri"] == "s3://b/k2"
