{{ config(materialized='table') }}

select distinct
    case commodity
        when 'rice' then 1
        when 'coffee' then 2
        when 'pepper' then 3
        when 'cashew' then 4
        when 'rubber' then 5
        when 'cocoa' then 6
        when 'cotton' then 7
    end as commodity_id,
    commodity,
    name_vi,
    category
from {{ ref('commodity_mapping') }}
where commodity in ('rice', 'coffee', 'pepper', 'cashew', 'rubber', 'cocoa', 'cotton')
