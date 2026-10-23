select r.route_id, r.route_short_name, r.route_long_name, r.route_type, a.agency_name
from {{ ref('stg_gtfs__routes') }} as r
left join {{ ref('stg_gtfs__agency') }} as a on r.agency_id = a.agency_id
