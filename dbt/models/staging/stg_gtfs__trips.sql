select
    trip_id,
    route_id,
    service_id,
    trip_headsign,
    try_cast(direction_id as integer) as direction_id
from {{ source('bronze_gtfs', 'trips') }}
