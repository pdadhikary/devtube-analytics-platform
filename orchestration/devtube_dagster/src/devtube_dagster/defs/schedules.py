import dagster as dg

from devtube_dagster.defs.jobs import devtube_ingestion_job

devtube_pipeline_schedule = dg.ScheduleDefinition(
    job=devtube_ingestion_job,
    cron_schedule="0 6 * * *",
    execution_timezone="Asia/Dhaka",
)
