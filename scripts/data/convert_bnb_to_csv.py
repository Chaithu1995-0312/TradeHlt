import pandas as pd
import os

def convert_excel_to_csv(excel_path):
    # 1. Load Excel file
    xl = pd.ExcelFile(excel_path)
    base_dir = os.path.dirname(excel_path)
    base_name = os.path.splitext(os.path.basename(excel_path))[0] # BNBUSDT_20240522_20260521
    
    print(f"Converting sheets from: {excel_path}")
    
    # 2. Iterate through sheets and save as CSV
    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name)
        output_csv = os.path.join(base_dir, f"{base_name}_{sheet_name}.csv")
        df.to_csv(output_csv, index=False)
        print(f"Saved {sheet_name} to {output_csv}")

if __name__ == "__main__":
    excel_path = r"data/yfinance/BNBUSDT_20240522_20260521.xlsx"
    if os.path.exists(excel_path):
        convert_excel_to_csv(excel_path)
    else:
        print(f"Error: File not found {excel_path}")
