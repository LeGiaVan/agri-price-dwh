{{ config(materialized='table') }}

with date_spine as (
    select cast(date_day as date) as date_day
    from generate_series(
        date '2000-01-01',
        cast(greatest(date '2026-12-31', current_date + interval 370 day) as date),
        interval 1 day
    ) as spine(date_day)
)

select
    cast(strftime(date_day, '%Y%m%d') as integer) as date_id,
    date_day as date,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month,
    strftime(date_day, '%B') as month_name,
    extract(week from date_day) as week,
    extract(dow from date_day) as day_of_week,
    case when extract(dow from date_day) in (0, 6) then true else false end as is_weekend,
    case
        when strftime(date_day, '%m-%d') in ('01-01', '04-30', '05-01', '09-02') then true
        else false
    end as is_vietnam_public_holiday
from date_spine
