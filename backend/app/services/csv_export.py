from pathlib import Path
import pandas as pd


def export_csv(df, file_id):
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    
    file_path = tmp_dir / f"{file_id}_result.csv"
    
    columns = ["Email", "total_orders", "total_items", "total_revenue"]
    df[columns].to_csv(file_path, index=False, encoding="utf-8-sig")
    
    return str(file_path)

