-- Typed view over every record ever delivered (duplicates included).
select
    event_id,
    service_date,
    trip_id,
    trim(stop_id) as stop_id,
    stop_sequence,
    upper(event_type) as event_type,
    upper(status) as status,
    actual_ts,
    recorded_at,
    source,
    cast(ingest_date as date) as ingest_date,
    _source_file as source_file,
    _source_line as source_line
from {{ source('bronze_events', 'events') }}
