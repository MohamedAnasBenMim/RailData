-- Clean, enriched stop events. Incremental: each run rebuilds the service
-- dates in [start_date - lookback_days, end_date] (partition overwrite via
-- delete+insert on service_date), so late events are picked up and re-runs
-- of the same window are idempotent.
{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='service_date',
        on_schema_change='fail'
    )
}}

select
    e.event_id,
    e.service_date,
    e.trip_id,
    t.route_id,
    t.direction_id,
    e.stop_id,
    e.stop_sequence,
    e.event_type,
    e.status,
    e.status = 'CANCELLED' as is_cancelled,
    e.scheduled_ts,
    e.actual_ts,
    round(e.delay_min, 2) as delay_min,
    case when e.status = 'OK' then e.delay_min < {{ var('on_time_threshold_min') }} end
        as is_on_time,
    hour(e.scheduled_ts) % 24 as scheduled_hour,
    dayofweek(e.service_date) in (0, 6) as is_weekend,
    e.recorded_at,
    e.ingest_date
from {{ ref('int_events_validated') }} as e
inner join {{ ref('stg_gtfs__trips') }} as t on e.trip_id = t.trip_id
where e.dq_reason is null
{% if is_incremental() and var('start_date') %}
  and e.service_date between
      cast('{{ var("start_date") }}' as date) - {{ var('lookback_days') }}
      and cast('{{ var("end_date", var("start_date")) }}' as date)
{% endif %}
