import csv
import os
from datetime import datetime

def filter_csv_file():
    input_file = '/home/marinhofn/tcc/refan/complete_unified_analysis.csv'
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_file = f'/home/marinhofn/tcc/refan/complete_unified_analysis_filtered_{timestamp}.csv'
    
    filtered_rows = []
    total_rows = 0
    excluded_rows = 0
    
    # Read the input CSV file
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        
        # Read header
        header = next(reader)
        filtered_rows.append(header)
        
        # Process each row
        for row in reader:
            total_rows += 1
            
            # Check if any cell contains 'none' or 'failed' (case-insensitive)
            contains_none_or_failed = any(
                'none' in str(cell).lower() or 'failed' in str(cell).lower() 
                for cell in row
            )
            
            if not contains_none_or_failed:
                filtered_rows.append(row)
            else:
                excluded_rows += 1
    
    # Write the filtered data to output file
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(filtered_rows)
    
    # Print summary
    print(f"Filtering completed!")
    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}")
    print(f"Total rows processed: {total_rows}")
    print(f"Rows excluded: {excluded_rows}")
    print(f"Rows included: {total_rows - excluded_rows}")
    print(f"Exclusion rate: {(excluded_rows / total_rows * 100):.2f}%")

if __name__ == "__main__":
    filter_csv_file()