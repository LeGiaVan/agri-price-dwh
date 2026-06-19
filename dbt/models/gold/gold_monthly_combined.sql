{{ config(materialized='table') }}

with wb_monthly as (
    select
        commodity,
        price_date as month_date,
        price_usd_per_kg,
        region,
        country,
        currency,
        source
    from {{ ref('silver_wb_prices') }}
),

yf_monthly as (
    select
        commodity,
        date_trunc('month', price_date) as month_date,
        avg(price_usd_per_kg) as price_usd_per_kg,
        region,
        country,
        currency,
        'YAHOO_FINANCE_MONTHLY_AVG' as source
    from {{ ref('silver_yf_prices') }}
    group by 1, 2, 4, 5, 6, 7
),

combined as (
    select * from wb_monthly
    union all
    select * from yf_monthly
)

select
    commodity,
    cast(month_date as date) as month_date,
    cast(price_usd_per_kg as decimal(18,6)) as price_usd_per_kg,
    region,
    country,
    currency,
    source
from combined
order by commodity, month_date desc, source
