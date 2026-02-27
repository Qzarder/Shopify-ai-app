import pandas as pd


def filter_orders(df):
    fs = df['Financial Status'].str.lower().fillna('')
    ff = df['Fulfillment Status'].str.lower().fillna('')

    filtered_df = df[
        (fs == 'paid') &
        (~fs.str.contains('refund')) &
        (~ff.str.contains('refund'))
    ].copy()

    
    return filtered_df

