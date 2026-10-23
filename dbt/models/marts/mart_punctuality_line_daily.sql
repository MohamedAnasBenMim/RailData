-- Daily punctuality and cancellation rate per line.
-- Punctuality is measured on realised arrivals at every served stop.
with arrivals as (
    select
        service_date,
        route_id,
        count(*) as n_arrivals,
        avg(case when is_on_time then 1.0 else 0.0 end) * 100 as on_time_pct,
        avg(delay_min) as avg_delay_min,
        quantile_cont(delay_min, 0.9) as p90_delay_min
    from {{ ref('fct_stop_events') }}
    where event_type = 'ARR' and not is_cancelled
    group by 1, 2
),

trips as (
    select
        service_date,
        route_id,
        count(*) as scheduled_trips,
        count(*) filter (where run_status = 'CANCELLED') as cancelled_trips,
        count(*) filter (where run_status = 'PARTIALLY_CANCELLED') as partially_cancelled_trips,
        count(*) filter (where run_status = 'NO_DATA') as no_data_trips
    from {{ ref('fct_trip_runs') }}
    group by 1, 2
)

select
    t.service_date,
    t.route_id,
    r.route_short_name,
    t.scheduled_trips,
    t.cancelled_trips,
    t.partially_cancelled_trips,
    t.no_data_trips,
    round(t.cancelled_trips / t.scheduled_trips, 4) as cancellation_rate,
    a.n_arrivals,
    round(a.on_time_pct, 2) as on_time_pct,
    round(a.avg_delay_min, 2) as avg_delay_min,
    round(a.p90_delay_min, 2) as p90_delay_min
from trips as t
left join arrivals as a on t.service_date = a.service_date and t.route_id = a.route_id
left join {{ ref('dim_routes') }} as r on t.route_id = r.route_id
