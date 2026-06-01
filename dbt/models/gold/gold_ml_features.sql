{{ config(materialized='table') }}

with daily_prices as (
    select
        fact.price_date,
        fact.commodity,
        dates.year,
        dates.quarter,
        dates.month,
        dates.week,
        dates.is_weekend,
        dates.is_vietnam_public_holiday,
        avg(fact.price_usd_per_kg) as price_usd_per_kg,
        avg(fact.price_change_pct) as price_change_pct,
        avg(fact.price_7d_avg) as price_7d_avg,
        avg(fact.price_30d_avg) as price_30d_avg,
        count(distinct fact.source) as source_count
    from {{ ref('fact_price_daily') }} as fact
    inner join {{ ref('dim_date') }} as dates
        on fact.date_id = dates.date_id
    group by
        fact.price_date,
        fact.commodity,
        dates.year,
        dates.quarter,
        dates.month,
        dates.week,
        dates.is_weekend,
        dates.is_vietnam_public_holiday
),

features as (
    select
        *,
        lag(price_usd_per_kg, 1) over (
            partition by commodity
            order by price_date
        ) as price_lag_1,
        lag(price_usd_per_kg, 7) over (
            partition by commodity
            order by price_date
        ) as price_lag_7,
        lag(price_usd_per_kg, 30) over (
            partition by commodity
            order by price_date
        ) as price_lag_30,
        avg(price_usd_per_kg) over (
            partition by commodity
            order by price_date
            rows between 89 preceding and current row
        ) as price_90d_avg,
        stddev_samp(price_usd_per_kg) over (
            partition by commodity
            order by price_date
            rows between 29 preceding and current row
        ) as price_30d_volatility
    from daily_prices
)

select
    price_date,
    commodity,
    year,
    quarter,
    month,
    week,
    is_weekend,
    is_vietnam_public_holiday,
    case
        when commodity = 'rice' and month between 6 and 9 then true
        when commodity = 'coffee' and month in (10, 11, 12, 1) then true
        when commodity = 'pepper' and month between 2 and 5 then true
        when commodity = 'cashew' and month between 2 and 4 then true
        when commodity = 'rubber' and month between 5 and 10 then true
        else false
    end as is_harvest_season,
    price_usd_per_kg,
    price_change_pct,
    price_7d_avg,
    price_30d_avg,
    price_90d_avg,
    price_30d_volatility,
    price_lag_1,
    price_lag_7,
    price_lag_30,
    source_count
from features
