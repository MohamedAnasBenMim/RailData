select stop_id, stop_name, stop_lat, stop_lon, location_type = 1 as is_hub
from {{ ref('stg_gtfs__stops') }}
