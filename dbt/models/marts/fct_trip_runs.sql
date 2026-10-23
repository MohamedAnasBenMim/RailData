-- One row per scheduled trip and service date, including trips with no data.
with ev as (
    select
        service_date,
        trip_id,
        count(*) as n_events,
        count(*) filter (where is_cancelled) as n_cancelled_events,
        arg_min(delay_min, stop_sequence) filter (where event_type = 'DEP' and not is_cancelled)
            as origin_departure_delay_min,
        arg_max(delay_min, stop_sequence) filter (where event_type = 'ARR' and not is_cancelled)
            as last_arrival_delay_min,
        max(delay_min) as max_delay_min
    from {{ ref('fct_stop_events') }}
    group by 1, 2
)

select
    s.service_date,
    s.trip_id,
    s.route_id,
    s.direction_id,
    coalesce(ev.n_events, 0) as n_events,
    case
        when ev.trip_id is null then 'NO_DATA'
        when ev.n_cancelled_events = ev.n_events then 'CANCELLED'
        when ev.n_cancelled_events > 0 then 'PARTIALLY_CANCELLED'
        else 'RAN'
    end as run_status,
    ev.origin_departure_delay_min,
    ev.last_arrival_delay_min,
    ev.max_delay_min,
    ev.last_arrival_delay_min - ev.origin_departure_delay_min as delay_gained_min
from {{ ref('int_scheduled_trips') }} as s
left join ev on s.service_date = ev.service_date and s.trip_id = ev.trip_id
where s.service_date in (select distinct service_date from {{ ref('fct_stop_events') }})
