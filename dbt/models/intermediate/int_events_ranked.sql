-- Rank every delivered version of an event. Version 1 (latest recorded_at,
-- then latest delivery) is the one we trust; the others are either exact
-- re-deliveries or older versions superseded by a correction.
with hashed as (
    select
        *,
        md5(concat_ws('|', service_date, trip_id, stop_id, stop_sequence, event_type,
                      status, actual_ts, recorded_at)) as payload_hash
    from {{ ref('stg_events') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by event_id
            order by recorded_at desc, ingest_date desc, source_line desc
        ) as version_rank
    from hashed
)

select
    r.*,
    case
        when r.version_rank = 1 then null
        when r.payload_hash = first_value(r.payload_hash) over (
            partition by r.event_id order by r.version_rank
        ) then 'duplicate_event'
        else 'superseded_version'
    end as dedup_reason
from ranked as r
