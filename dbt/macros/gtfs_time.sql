{# GTFS times are "HH:MM:SS" relative to the service day and may exceed 24:00. #}
{% macro gtfs_time_to_seconds(col) -%}
case when {{ col }} is null or {{ col }} = '' then null else
  cast(split_part({{ col }}, ':', 1) as integer) * 3600
  + cast(split_part({{ col }}, ':', 2) as integer) * 60
  + cast(split_part({{ col }}, ':', 3) as integer)
end
{%- endmacro %}
