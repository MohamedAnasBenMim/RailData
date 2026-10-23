-- Punctuality of arrivals per station, over the whole processed history.
select
    s.stop_id,
    s.stop_name,
    s.is_hub,
    count(*) as n_arrivals,
    round(avg(case when e.is_on_time then 1.0 else 0.0 end) * 100, 2) as on_time_pct,
    round(avg(e.delay_min), 2) as avg_delay_min,
    round(quantile_cont(e.delay_min, 0.9), 2) as p90_delay_min
from {{ ref('fct_stop_events') }} as e
inner join {{ ref('dim_stops') }} as s on e.stop_id = s.stop_id
where e.event_type = 'ARR' and not e.is_cancelled
group by 1, 2, 3
