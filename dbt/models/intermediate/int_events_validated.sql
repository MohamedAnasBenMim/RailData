-- One row per event_id (latest version) with schedule attached and the first
-- failing data-quality rule in `dq_reason` (null = clean).
-- Rules are evaluated in order; the out-of-order check only looks at events
-- that passed the earlier rules, so one bad record cannot taint its neighbours.
with latest as (
    select * from {{ ref('int_events_ranked') }} where version_rank = 1
),

joined as (
    select
        e.event_id,
        e.service_date,
        e.trip_id,
        e.stop_id,
        e.stop_sequence,
        e.event_type,
        e.status,
        e.actual_ts,
        e.recorded_at,
        e.ingest_date,
        e.source_file,
        s.stop_id is not null as stop_known,
        st.trip_id is not null as stop_time_found,
        st.stop_id as scheduled_stop_id,
        e.service_date + to_seconds(
            case when e.event_type = 'ARR' then st.arrival_offset_s else st.departure_offset_s end
        ) as scheduled_ts
    from latest as e
    left join {{ ref('stg_gtfs__stops') }} as s on e.stop_id = s.stop_id
    left join {{ ref('stg_gtfs__stop_times') }} as st
        on e.trip_id = st.trip_id and e.stop_sequence = st.stop_sequence
),

rules as (
    select
        *,
        date_diff('second', scheduled_ts, actual_ts) / 60.0 as delay_min,
        case
            when not stop_known then 'unknown_stop_id'
            when not stop_time_found then 'no_matching_stop_time'
            when stop_id <> scheduled_stop_id then 'stop_mismatch'
            when status = 'OK' and actual_ts is null then 'missing_actual_ts'
            when status = 'CANCELLED' and actual_ts is not null then 'cancelled_with_actual_ts'
            when status = 'OK'
                and (date_diff('second', scheduled_ts, actual_ts) > {{ var('max_delay_min') }} * 60
                     or date_diff('second', scheduled_ts, actual_ts) < {{ var('min_delay_min') }} * 60)
                then 'implausible_delay'
        end as row_rule_failure
    from joined
),

sequenced as (
    select
        *,
        lag(actual_ts) over (
            partition by service_date, trip_id
            order by stop_sequence, case event_type when 'ARR' then 0 else 1 end
        ) as prev_actual_ts
    from rules
    where row_rule_failure is null and actual_ts is not null
)

select
    r.event_id,
    r.service_date,
    r.trip_id,
    r.stop_id,
    r.stop_sequence,
    r.event_type,
    r.status,
    r.scheduled_ts,
    r.actual_ts,
    r.delay_min,
    r.recorded_at,
    r.ingest_date,
    r.source_file,
    coalesce(
        r.row_rule_failure,
        case when s.actual_ts < s.prev_actual_ts - interval 60 second
             then 'out_of_order_timestamp' end
    ) as dq_reason
from rules as r
left join sequenced as s on r.event_id = s.event_id
