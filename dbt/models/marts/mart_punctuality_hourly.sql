-- Punctuality of arrivals by scheduled hour of day, weekday vs weekend.
select
    case when is_weekend then 'weekend' else 'weekday' end as day_type,
    scheduled_hour,
    count(*) as n_arrivals,
    round(avg(case when is_on_time then 1.0 else 0.0 end) * 100, 2) as on_time_pct,
    round(avg(delay_min), 2) as avg_delay_min,
    round(quantile_cont(delay_min, 0.9), 2) as p90_delay_min
from {{ ref('fct_stop_events') }}
where event_type = 'ARR' and not is_cancelled
group by 1, 2
