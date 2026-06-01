{{ config(materialized='table') }}

{% set wb_source = source('bronze', 'wb_prices_raw') %}

with raw as (
    select *
    from {{ wb_source }}
),

typed as (
    select
        {{ column_or_null(wb_source, ['commodity', 'indicator_name', 'item', 'product', 'product_name', 'name']) }} as raw_commodity,
        {{ column_or_null(wb_source, ['date', 'price_date', 'period', 'year_month', 'month_date']) }} as raw_date,
        {{ column_or_null(wb_source, ['year'], 'integer') }} as raw_year,
        {{ column_or_null(wb_source, ['month'], 'integer') }} as raw_month,
        {{ column_or_null(wb_source, ['region', 'market', 'market_name', 'area', 'province']) }} as raw_region,
        {{ column_or_null(wb_source, ['country', 'country_name']) }} as raw_country,
        {{ column_or_null(wb_source, ['price', 'value', 'price_usd', 'price_usd_per_kg'], 'decimal(18,6)') }} as raw_price,
        {{ column_or_null(wb_source, ['currency']) }} as raw_currency,
        {{ column_or_null(wb_source, ['unit', 'price_unit']) }} as raw_unit,
        {{ column_or_null(wb_source, ['ingested_at', 'loaded_at', 'created_at'], 'timestamp') }} as ingested_at
    from raw
),

standardized as (
    select
        coalesce(mapping.commodity, lower(trim(typed.raw_commodity))) as commodity,
        coalesce(
            try_cast(typed.raw_date as date),
            case
                when typed.raw_year is not null and typed.raw_month between 1 and 12
                    then make_date(typed.raw_year, typed.raw_month, 1)
                when typed.raw_year is not null
                    then make_date(typed.raw_year, 1, 1)
            end
        ) as price_date,
        coalesce(nullif(trim(typed.raw_region), ''), 'global') as region,
        coalesce(nullif(trim(typed.raw_country), ''), 'World') as country,
        case
            when lower(coalesce(typed.raw_unit, '')) like '%ton%' then typed.raw_price / 1000
            when lower(coalesce(typed.raw_unit, '')) in ('t', 'mt') then typed.raw_price / 1000
            when lower(coalesce(typed.raw_unit, '')) like '%lb%' then typed.raw_price / 0.45359237
            else typed.raw_price
        end as price_usd_per_kg,
        coalesce(upper(nullif(trim(typed.raw_currency), '')), 'USD') as currency,
        coalesce(nullif(trim(typed.raw_unit), ''), 'kg') as unit,
        'WORLD_BANK' as source,
        coalesce(typed.ingested_at, current_timestamp) as ingested_at
    from typed
    left join {{ ref('commodity_mapping') }} as mapping
        on lower(trim(typed.raw_commodity)) = lower(mapping.raw_name)
        or lower(trim(typed.raw_commodity)) = lower(mapping.commodity)
),

deduplicated as (
    select
        *,
        row_number() over (
            partition by commodity, price_date, region, source
            order by ingested_at desc
        ) as row_number
    from standardized
    where commodity in ('rice', 'coffee', 'pepper', 'cashew', 'rubber')
        and price_date is not null
        and price_usd_per_kg is not null
        and price_usd_per_kg > 0
)

select
    commodity,
    price_date,
    region,
    country,
    cast(price_usd_per_kg as decimal(18,6)) as price_usd_per_kg,
    currency,
    unit,
    source,
    ingested_at
from deduplicated
where row_number = 1
