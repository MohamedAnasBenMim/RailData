-- Every delivered record that did not make it to the clean layer, with why.
-- bronze rows = clean rows + quarantined rows (checked by a singular test).
select
    event_id, service_date, trip_id, stop_id, stop_sequence, event_type, status,
    actual_ts, recorded_at, ingest_date, source_file,
    dedup_reason as dq_reason
from {{ ref('int_events_ranked') }}
where dedup_reason is not null

union all

select
    event_id, service_date, trip_id, stop_id, stop_sequence, event_type, status,
    actual_ts, recorded_at, ingest_date, source_file,
    dq_reason
from {{ ref('int_events_validated') }}
where dq_reason is not null
