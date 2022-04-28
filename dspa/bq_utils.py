from typing import Any, Dict, List, Sequence

from consts import PROJECT_ID, DATSET_NAME, ENTITIES_TABLE_NAME

from google.cloud import bigquery

bq_client = bigquery.Client()


def write_to_bq(
    entities: List[Dict[str, Any]],
    project_id: str = PROJECT_ID,
    dataset_name: str = DATSET_NAME,
    table_name: str = ENTITIES_TABLE_NAME,
) -> Sequence[dict]:
    """
    Write Data to BigQuery
    """
    dataset_ref = bq_client.dataset(dataset_name, project=project_id)
    table = bq_client.get_table(dataset_ref.table(table_name))

    job = bq_client.insert_rows(
        table, entities, skip_invalid_rows=True, ignore_unknown_values=True
    )

    return job
