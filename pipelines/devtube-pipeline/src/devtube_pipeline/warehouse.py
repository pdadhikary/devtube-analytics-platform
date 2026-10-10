import structlog
from pyarrow import Table as ArrowTable
from pyiceberg.catalog import Catalog
from pyiceberg.schema import Schema
from pyiceberg.table import UpsertResult

logger = structlog.get_logger(__name__)


def ensure_table_and_upsert(
    catalog: Catalog,
    namespace: str,
    table_name: str,
    location: str,
    schema: Schema,
    arrow_table: ArrowTable,
    join_cols: list[str],
) -> UpsertResult:
    if not catalog.namespace_exists(namespace):
        catalog.create_namespace(namespace)

    table = catalog.create_table_if_not_exists(
        schema=schema,
        identifier=f"{namespace}.{table_name}",
        location=location,
    )

    return table.upsert(
        arrow_table,
        join_cols=join_cols,
        when_matched_update_all=True,
        when_not_matched_insert_all=True,
    )
