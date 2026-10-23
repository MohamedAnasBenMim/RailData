select
    service_id,
    strptime("date", '%Y%m%d')::date as service_date,
    cast(exception_type as integer) as exception_type  -- 1 = added, 2 = removed
from {{ source('bronze_gtfs', 'calendar_dates') }}
