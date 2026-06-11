{{ config(materialized='table') }}

{% set yf_source = source('bronze', 'yf_prices_raw') %}

with raw as (
    select *
    from {{ yf_source }}
),

typed as (
    select
        {{ column_or_null(yf_source, ['commodity', 'product', 'product_name']) }} as raw_commodity,
        {{ column_or_null(yf_source, ['price_date', 'date', 'period']) }} as raw_date,
        {{ column_or_null(yf_source, ['price_usd_per_kg'], 'decimal(18,6)') }} as raw_price_usd_per_kg,
        {{ column_or_null(yf_source, ['price_usd', 'close'], 'decimal(18,6)') }} as raw_close,
        {{ column_or_null(yf_source, ['ticker', 'symbol']) }} as raw_ticker,
        {{ column_or_null(yf_source, ['raw_unit', 'unit', 'price_unit']) }} as raw_unit,
        {{ column_or_null(yf_source, ['region', 'market']) }} as raw_region,
        {{ column_or_null(yf_source, ['country', 'country_name']) }} as raw_country,
        {{ column_or_null(yf_source, ['currency']) }} as raw_currency,
        {{ column_or_null(yf_source, ['ingested_at', 'loaded_at', 'created_at'], 'timestamp') }} as ingested_at
    from raw
),

standardized as (
    select
        coalesce(mapping.commodity, lower(trim(typed.raw_commodity))) as commodity,
        try_cast(typed.raw_date as date) as price_date,
        coalesce(nullif(trim(typed.raw_region), ''), 'US futures market') as region,
        coalesce(nullif(trim(typed.raw_country), ''), 'United States') as country,
        coalesce(
            typed.raw_price_usd_per_kg,
            case
                when lower(coalesce(typed.raw_unit, '')) = 'cents/lb'
                    or typed.raw_ticker in ('KC=F', 'CT=F')
                    then (typed.raw_close / 100) / 0.45359237
                when lower(coalesce(typed.raw_unit, '')) = 'cents/cwt'
                    or typed.raw_ticker = 'ZR=F'
                    then (typed.raw_close / 100) / 45.359237
                when lower(coalesce(typed.raw_unit, '')) in ('usd/metric_ton', 'usd/mt')
                    or typed.raw_ticker = 'CC=F'
                    then typed.raw_close / 1000
            end
        ) as price_usd_per_kg,
        typed.raw_close as close_price,
        coalesce(nullif(trim(typed.raw_ticker), ''), 'unknown') as ticker,
        coalesce(nullif(trim(typed.raw_unit), ''), 'unknown') as unit,
        coalesce(upper(nullif(trim(typed.raw_currency), '')), 'USD') as currency,
        'YAHOO_FINANCE' as source,
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
    where commodity in ('rice', 'coffee', 'cocoa', 'cotton')
        and price_date is not null
        and price_usd_per_kg is not null
        and price_usd_per_kg > 0
),

base_prices as (
    select
        commodity,
        price_date,
        region,
        country,
        cast(price_usd_per_kg as decimal(18,6)) as price_usd_per_kg,
        cast(close_price as decimal(18,6)) as close_price,
        currency,
        unit,
        ticker,
        source,
        ingested_at
    from deduplicated
    where row_number = 1
),

date_bounds as (
    select
        commodity,
        region,
        country,
        currency,
        unit,
        ticker,
        source,
        min(price_date) as min_date,
        max(price_date) as max_date
    from base_prices
    group by commodity, region, country, currency, unit, ticker, source
),

calendar as (
    select
        bounds.commodity,
        dates.date as price_date,
        bounds.region,
        bounds.country,
        bounds.currency,
        bounds.unit,
        bounds.ticker,
        bounds.source,
        dates.is_weekend
    from date_bounds as bounds
    inner join {{ ref('dim_date') }} as dates
        on dates.date between bounds.min_date and bounds.max_date
),

joined as (
    select
        calendar.*,
        base_prices.price_usd_per_kg,
        base_prices.close_price,
        base_prices.ingested_at
    from calendar
    left join base_prices
        on calendar.commodity = base_prices.commodity
        and calendar.price_date = base_prices.price_date
        and calendar.region = base_prices.region
        and calendar.source = base_prices.source
),

filled as (
    select
        *,
        last_value(price_usd_per_kg ignore nulls) over (
            partition by commodity, region, source
            order by price_date
            rows between unbounded preceding and current row
        ) as filled_price_usd_per_kg,
        last_value(close_price ignore nulls) over (
            partition by commodity, region, source
            order by price_date
            rows between unbounded preceding and current row
        ) as filled_close_price,
        last_value(case when price_usd_per_kg is not null then price_date end ignore nulls) over (
            partition by commodity, region, source
            order by price_date
            rows between unbounded preceding and current row
        ) as last_observed_date,
        last_value(ingested_at ignore nulls) over (
            partition by commodity, region, source
            order by price_date
            rows between unbounded preceding and current row
        ) as filled_ingested_at
    from joined
)

select
    commodity,
    price_date,
    region,
    country,
    cast(filled_price_usd_per_kg as decimal(18,6)) as price_usd_per_kg,
    currency,
    unit,
    source,
    coalesce(filled_ingested_at, current_timestamp) as ingested_at,
    ticker,
    cast(filled_close_price as decimal(18,6)) as close_price,
    price_usd_per_kg is null as is_imputed
from filled
where price_usd_per_kg is not null
    or (
        is_weekend
        and filled_price_usd_per_kg is not null
        and date_diff('day', last_observed_date, price_date) between 1 and 3
    )
