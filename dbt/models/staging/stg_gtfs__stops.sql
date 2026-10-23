select
    stop_id,
    stop_name,
    try_cast(stop_lat as double) as stop_lat,
    try_cast(stop_lon as double) as stop_lon,
    coalesce(try_cast(location_type as integer), 0) as location_type,
    nullif(parent_station, '') as parent_station
from {{ source('bronze_gtfs', 'stops') }}
