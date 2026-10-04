import pandas as pd
import os
import math

def split_csv_to_excel(file_path, num_sheets=5):
    # 1. Read Data
    df = pd.read_csv(file_path)
    
    # 2. Determine start and end dates for filename
    # Assuming 'timestamp' column exists based on previous check
    start_date = pd.to_datetime(df['timestamp'].iloc[0]).strftime('%Y%m%d')
    end_date = pd.to_datetime(df['timestamp'].iloc[-1]).strftime('%Y%m%d')
    coin_name = os.path.basename(file_path).split('_')[0]
    
    output_filename = f"{coin_name}_{start_date}_{end_date}.xlsx"
    output_path = os.path.join(os.path.dirname(file_path), output_filename)
    
    # 3. Split data into chunks
    rows_per_sheet = math.ceil(len(df) / num_sheets)
    
    print(f"Total rows: {len(df)}")
    print(f"Rows per sheet: {rows_per_sheet}")
    print(f"Exporting to: {output_path}")
    
    # 4. Create Excel file with 5 sheets
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for i in range(num_sheets):
            start_idx = i * rows_per_sheet
            end_idx = min((i + 1) * rows_per_sheet, len(df))
            
            chunk = df.iloc[start_idx:end_idx]
            sheet_name = f"Part_{i+1}"
            chunk.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"Wrote {len(chunk)} rows to {sheet_name}")

    print("Successfully completed split.")

if __name__ == "__main__":
    csv_path = r"data/yfinance/BNBUSDT_M15.csv"
    split_csv_to_excel(csv_path)
