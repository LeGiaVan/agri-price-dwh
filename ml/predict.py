import pandas as pd

from ml.common import (
    COMMODITIES,
    ensure_gold_tables,
    motherduck_connection,
)


def main() -> None:
    con = motherduck_connection()
    ensure_gold_tables(con)

    forecast_df = con.execute("""
        select
            date as forecast_date,
            commodity,
            predicted_price,
            model_name,
            current_timestamp as created_at
        from gold.forecast_lstm
    """).fetchdf()

    if not forecast_df.empty:
        con.execute("delete from gold.fact_forecasts")

        con.register("forecast_df", forecast_df)

        con.execute("""
            insert into gold.fact_forecasts
            select *
            from forecast_df
        """)

        con.unregister("forecast_df")

        print(f"Inserted {len(forecast_df)} rows")

    con.close()


if __name__ == "__main__":
    main()