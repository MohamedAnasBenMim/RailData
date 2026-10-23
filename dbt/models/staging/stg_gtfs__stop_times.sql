select
    trip_id,
    stop_id,
    cast(stop_sequence as integer) as stop_sequence,
    {{ gtfs_time_to_seconds('arrival_time') }} as arrival_offset_s,
    {{ gtfs_time_to_seconds('departure_time') }} as departure_offset_s
from {{ source('bronze_gtfs', 'stop_times') }}
