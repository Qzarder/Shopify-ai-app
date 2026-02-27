import csv
from pathlib import Path


def validate_shopify_csv(file_path):
    required_columns = [
        "Name",
        "Email",
        "Financial Status",
        "Fulfillment Status",
        "Lineitem quantity",
        "Lineitem price",
        "Created at"
    ]
    
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        if header is None:
            raise ValueError("CSV file is empty")
        
        header_normalized = [col.strip().lower() for col in header]
        missing_columns = []
        
        for required_col in required_columns:
            if required_col.lower() not in header_normalized:
                missing_columns.append(required_col)
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

