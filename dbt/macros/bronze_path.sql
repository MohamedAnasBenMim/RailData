{# Absolute or relative path of the bronze layer (set by the raildata CLI). #}
{% macro bronze_path(rel) -%}
{{ env_var('RAILDATA_DATA_DIR', '../data') }}/bronze/{{ rel }}
{%- endmacro %}
