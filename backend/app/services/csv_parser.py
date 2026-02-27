import pandas as pd
from pathlib import Path


def parse_orders_csv(file_path):
    path = Path(file_path)
    
    encodings = ['utf-8', 'utf-8-sig']
    df = None
    
    for encoding in encodings:
        try:
            df = pd.read_csv(path, encoding=encoding, dtype=str)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if df is None:
        raise ValueError(f"Could not decode file {file_path} with any supported encoding")
    
    df = df.dropna(how='all')
    
    return df

