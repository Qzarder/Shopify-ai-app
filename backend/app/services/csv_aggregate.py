import pandas as pd


def aggregate_orders(df):
    df_copy = df.copy()

    df_copy['quantity'] = pd.to_numeric(
        df_copy['Lineitem quantity'], errors='coerce'
    ).fillna(0)

    df_copy['price'] = pd.to_numeric(
        df_copy['Lineitem price'], errors='coerce'
    ).fillna(0)

    df_copy['revenue'] = df_copy['quantity'] * df_copy['price']

    aggregated = (
        df_copy
        .groupby('Email')
        .agg(
            total_orders=('Name', 'nunique'),
            total_items=('quantity', 'sum'),
            total_revenue=('revenue', 'sum')
        )
        .reset_index()
    )

    return aggregated

