-- Every delivered record is accounted for: bronze = clean + quarantined.
with c as (
    select
        (select count(*) from {{ ref('stg_events') }}) as bronze_rows,
        (select count(*) from {{ ref('int_events_validated') }} where dq_reason is null)
            as clean_rows,
        (select count(*) from {{ ref('dq_quarantine_events') }}) as quarantined_rows
)
select * from c where bronze_rows <> clean_rows + quarantined_rows
