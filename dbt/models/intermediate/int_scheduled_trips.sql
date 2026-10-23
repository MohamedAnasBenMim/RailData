-- Expand the GTFS calendar into one row per (service_date, trip), honouring
-- calendar_dates exceptions. A service date is only reported once its own
-- daily delivery has been ingested (a date seen only through late events
-- from the next delivery would otherwise look like mass "no data").
with dates as (
    select distinct service_date from {{ ref('stg_events') }}
    intersect
    select distinct ingest_date from {{ ref('stg_events') }}
),

regular as (
    select d.service_date, c.service_id
    from dates as d
    inner join {{ ref('stg_gtfs__calendar') }} as c
        on d.service_date between c.start_date and c.end_date
        and case dayofweek(d.service_date)
            when 0 then c.sunday when 1 then c.monday when 2 then c.tuesday
            when 3 then c.wednesday when 4 then c.thursday when 5 then c.friday
            else c.saturday end
),

active as (
    select r.service_date, r.service_id
    from regular as r
    left join {{ ref('stg_gtfs__calendar_dates') }} as removed
        on r.service_date = removed.service_date
        and r.service_id = removed.service_id
        and removed.exception_type = 2
    where removed.service_id is null
    union
    select cd.service_date, cd.service_id
    from {{ ref('stg_gtfs__calendar_dates') }} as cd
    inner join dates as d on cd.service_date = d.service_date
    where cd.exception_type = 1
)

select
    a.service_date,
    t.trip_id,
    t.route_id,
    t.direction_id
from active as a
inner join {{ ref('stg_gtfs__trips') }} as t on a.service_id = t.service_id
