select event_id
from {{ ref('fct_stop_events') }}
where (is_cancelled and actual_ts is not null)
   or (not is_cancelled and (actual_ts is null or delay_min is null))
