select
    coalesce(nullif(agency_id, ''), 'DEFAULT') as agency_id,
    agency_name,
    agency_url,
    agency_timezone
from {{ source('bronze_gtfs', 'agency') }}
