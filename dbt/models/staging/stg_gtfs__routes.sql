select
    route_id,
    coalesce(nullif(agency_id, ''), 'DEFAULT') as agency_id,
    coalesce(nullif(route_short_name, ''), route_id) as route_short_name,
    route_long_name,
    cast(route_type as integer) as route_type
from {{ source('bronze_gtfs', 'routes') }}
