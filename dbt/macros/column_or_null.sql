{% macro column_or_null(relation, candidates, cast_type='varchar') -%}
    {%- if execute -%}
        {%- set columns = adapter.get_columns_in_relation(relation) -%}
        {%- set match = namespace(name=none) -%}
        {%- for column in columns -%}
            {%- for candidate in candidates -%}
                {%- if column.name | lower == candidate | lower and match.name is none -%}
                    {%- set match.name = column.name -%}
                {%- endif -%}
            {%- endfor -%}
        {%- endfor -%}
        {%- if match.name is not none -%}
            try_cast({{ adapter.quote(match.name) }} as {{ cast_type }})
        {%- else -%}
            cast(null as {{ cast_type }})
        {%- endif -%}
    {%- else -%}
        cast(null as {{ cast_type }})
    {%- endif -%}
{%- endmacro %}
