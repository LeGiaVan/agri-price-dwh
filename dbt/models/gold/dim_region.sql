{{ config(materialized='table') }}

with regions as (
    select distinct
        country,
        region,
        source
    from {{ ref('silver_wb_prices') }}

    union

    select distinct
        country,
        region,
        source
    from {{ ref('silver_yf_prices') }}
)

select
    row_number() over (order by country, region, source) as region_id,
    country,
    region,
    source,
    case
        when lower(country) in ('vietnam', 'viet nam') then true
        else false
    end as is_vietnam_market
from regions
