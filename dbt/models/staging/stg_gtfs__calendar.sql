select
    service_id,
    monday = '1' as monday,
    tuesday = '1' as tuesday,
    wednesday = '1' as wednesday,
    thursday = '1' as thursday,
    friday = '1' as friday,
    saturday = '1' as saturday,
    sunday = '1' as sunday,
    strptime(start_date, '%Y%m%d')::date as start_date,
    strptime(end_date, '%Y%m%d')::date as end_date
from {{ source('bronze_gtfs', 'calendar') }}
