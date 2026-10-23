-- Within a trip run, clean realised timestamps never go back in time
-- by more than the 60 s tolerance used by the validation rule.
select *
from (
    select
        event_id,
        actual_ts,
        lag(actual_ts) over (
            partition by service_date, trip_id
            order by stop_sequence, case event_type when 'ARR' then 0 else 1 end
        ) as prev_actual_ts
    from {{ ref('fct_stop_events') }}
    where actual_ts is not null
)
where actual_ts < prev_actual_ts - interval 60 second
