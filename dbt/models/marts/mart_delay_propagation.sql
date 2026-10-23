-- How delay builds up (or is recovered) along a trip: mean delay at each
-- stop of each line/direction, and the change versus the previous stop.
with by_stop as (
    select
        e.route_id,
        e.direction_id,
        e.stop_sequence,
        e.stop_id,
        count(*) as n_events,
        avg(e.delay_min) as avg_delay_min,
        quantile_cont(e.delay_min, 0.9) as p90_delay_min
    from {{ ref('fct_stop_events') }} as e
    where not e.is_cancelled
      -- departure delay at the origin, arrival delay everywhere else
      and ((e.stop_sequence = 1 and e.event_type = 'DEP') or e.event_type = 'ARR')
    group by 1, 2, 3, 4
)

select
    b.route_id,
    b.direction_id,
    b.stop_sequence,
    b.stop_id,
    s.stop_name,
    b.n_events,
    round(b.avg_delay_min, 2) as avg_delay_min,
    round(b.p90_delay_min, 2) as p90_delay_min,
    round(b.avg_delay_min - lag(b.avg_delay_min) over (
        partition by b.route_id, b.direction_id order by b.stop_sequence
    ), 2) as delta_vs_prev_stop_min
from by_stop as b
left join {{ ref('dim_stops') }} as s on b.stop_id = s.stop_id
