{{ config(materialized='table') }}

with prices as (
    select * from {{ ref('silver_fao_prices') }}
    union all
    select * from {{ ref('silver_wb_prices') }}
),

joined as (
    select
        cast(md5(
            prices.source || '|' ||
            prices.commodity || '|' ||
            cast(prices.price_date as varchar) || '|' ||
            prices.region
        ) as varchar) as price_id,
        commodity.commodity_id,
        dates.date_id,
        region.region_id,
        prices.price_date,
        prices.commodity,
        prices.region,
        prices.country,
        prices.price_usd_per_kg,
        prices.currency,
        prices.unit,
        prices.source,
        prices.ingested_at
    from prices
    inner join {{ ref('dim_commodity') }} as commodity
        on prices.commodity = commodity.commodity
    inner join {{ ref('dim_date') }} as dates
        on prices.price_date = dates.date
    inner join {{ ref('dim_region') }} as region
        on prices.country = region.country
        and prices.region = region.region
        and prices.source = region.source
),

metrics as (
    select
        *,
        lag(price_usd_per_kg) over (
            partition by commodity_id, region_id, source
            order by price_date
        ) as previous_price_usd_per_kg,
        avg(price_usd_per_kg) over (
            partition by commodity_id, region_id, source
            order by price_date
            rows between 6 preceding and current row
        ) as price_7d_avg,
        avg(price_usd_per_kg) over (
            partition by commodity_id, region_id, source
            order by price_date
            rows between 29 preceding and current row
        ) as price_30d_avg
    from joined
)

select
    price_id,
    commodity_id,
    date_id,
    region_id,
    price_date,
    commodity,
    region,
    country,
    price_usd_per_kg,
    previous_price_usd_per_kg,
    case
        when previous_price_usd_per_kg is null or previous_price_usd_per_kg = 0 then null
        else ((price_usd_per_kg - previous_price_usd_per_kg) / previous_price_usd_per_kg) * 100
    end as price_change_pct,
    price_7d_avg,
    price_30d_avg,
    currency,
    unit,
    source,
    ingested_at
from metrics
