"""
Dataset Explorer for ESG Project
Analyzes all CSV files in data/ folder and generates comprehensive summary
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

def get_file_size(filepath):
    """Get human-readable file size"""
    size = os.path.getsize(filepath)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def identify_column_types(df):
    """Identify common ESG-related columns"""
    columns_lower = {col.lower(): col for col in df.columns}
    
    identified = {
        'company_name': None,
        'esg_score': None,
        'industry': None,
        'date': None
    }
    
    # Company name patterns
    company_patterns = ['company', 'name', 'ticker', 'symbol', 'organization']
    for pattern in company_patterns:
        for col_lower, col_original in columns_lower.items():
            if pattern in col_lower and identified['company_name'] is None:
                identified['company_name'] = col_original
                break
    
    # ESG score patterns
    esg_patterns = ['esg', 'score', 'rating', 'sustainability']
    for pattern in esg_patterns:
        for col_lower, col_original in columns_lower.items():
            if pattern in col_lower and identified['esg_score'] is None:
                identified['esg_score'] = col_original
                break
    
    # Industry patterns
    industry_patterns = ['industry', 'sector', 'category']
    for pattern in industry_patterns:
        for col_lower, col_original in columns_lower.items():
            if pattern in col_lower and identified['industry'] is None:
                identified['industry'] = col_original
                break
    
    # Date patterns
    date_patterns = ['date', 'time', 'year', 'period']
    for pattern in date_patterns:
        for col_lower, col_original in columns_lower.items():
            if pattern in col_lower and identified['date'] is None:
                identified['date'] = col_original
                break
    
    return identified

def analyze_csv(filepath):
    """Analyze a single CSV file"""
    try:
        # Read CSV
        df = pd.read_csv(filepath)
        
        analysis = {
            'filename': os.path.basename(filepath),
            'filepath': filepath,
            'size': get_file_size(filepath),
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': list(df.columns),
            'dtypes': df.dtypes.to_dict(),
            'missing_values': df.isnull().sum().to_dict(),
            'identified_columns': identify_column_types(df),
            'sample_data': df.head(5),
            'success': True
        }
        
        return analysis
    
    except Exception as e:
        return {
            'filename': os.path.basename(filepath),
            'filepath': filepath,
            'error': str(e),
            'success': False
        }

def generate_report(analyses, output_file):
    """Generate comprehensive report"""
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("ESG PROJECT - DATASET EXPLORATION REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total CSV files found: {len(analyses)}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    successful = [a for a in analyses if a['success']]
    failed = [a for a in analyses if not a['success']]
    
    # Summary statistics
    if successful:
        total_rows = sum(a['rows'] for a in successful)
        total_columns = sum(a['columns'] for a in successful)
        
        report_lines.append("SUMMARY STATISTICS")
        report_lines.append("-" * 80)
        report_lines.append(f"Successfully analyzed: {len(successful)} files")
        report_lines.append(f"Failed to analyze: {len(failed)} files")
        report_lines.append(f"Total rows across all files: {total_rows:,}")
        report_lines.append(f"Average columns per file: {total_columns / len(successful):.1f}")
        report_lines.append("")
    
    # Individual file analyses
    for i, analysis in enumerate(successful, 1):
        report_lines.append("=" * 80)
        report_lines.append(f"FILE {i}: {analysis['filename']}")
        report_lines.append("=" * 80)
        report_lines.append(f"Path: {analysis['filepath']}")
        report_lines.append(f"Size: {analysis['size']}")
        report_lines.append(f"Rows: {analysis['rows']:,}")
        report_lines.append(f"Columns: {analysis['columns']}")
        report_lines.append("")
        
        # Column information
        report_lines.append("COLUMNS AND DATA TYPES")
        report_lines.append("-" * 80)
        for col, dtype in analysis['dtypes'].items():
            missing = analysis['missing_values'][col]
            missing_pct = (missing / analysis['rows'] * 100) if analysis['rows'] > 0 else 0
            report_lines.append(f"  {col:30s} | {str(dtype):15s} | Missing: {missing:6d} ({missing_pct:5.1f}%)")
        report_lines.append("")
        
        # Identified ESG columns
        report_lines.append("IDENTIFIED ESG-RELATED COLUMNS")
        report_lines.append("-" * 80)
        identified = analysis['identified_columns']
        report_lines.append(f"  Company Name:  {identified['company_name'] or 'Not found'}")
        report_lines.append(f"  ESG Score:     {identified['esg_score'] or 'Not found'}")
        report_lines.append(f"  Industry:      {identified['industry'] or 'Not found'}")
        report_lines.append(f"  Date:          {identified['date'] or 'Not found'}")
        report_lines.append("")
        
        # Sample data
        report_lines.append("SAMPLE DATA (First 5 rows)")
        report_lines.append("-" * 80)
        sample_str = analysis['sample_data'].to_string(max_rows=5, max_cols=10)
        report_lines.append(sample_str)
        report_lines.append("")
        report_lines.append("")
    
    # Failed files
    if failed:
        report_lines.append("=" * 80)
        report_lines.append("FAILED TO ANALYZE")
        report_lines.append("=" * 80)
        for analysis in failed:
            report_lines.append(f"File: {analysis['filename']}")
            report_lines.append(f"Error: {analysis['error']}")
            report_lines.append("")
    
    # Footer
    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)
    
    # Write to file
    report_text = "\n".join(report_lines)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    return report_text

def main():
    """Main execution function"""
    print("=" * 80)
    print("ESG DATASET EXPLORER")
    print("=" * 80)
    
    # Find data directory
    data_dir = Path('data')
    if not data_dir.exists():
        print(f"❌ Error: 'data/' directory not found")
        print(f"   Current directory: {os.getcwd()}")
        print(f"   Please run this script from the project root directory")
        return
    
    # Find all CSV files
    csv_files = list(data_dir.glob('**/*.csv'))
    
    if not csv_files:
        print(f"❌ No CSV files found in {data_dir}")
        return
    
    print(f"\n📁 Found {len(csv_files)} CSV file(s) in data/ directory")
    print("")
    
    # Analyze each file
    analyses = []
    for i, csv_file in enumerate(csv_files, 1):
        print(f"[{i}/{len(csv_files)}] Analyzing: {csv_file.name}...", end=' ')
        analysis = analyze_csv(csv_file)
        analyses.append(analysis)
        
        if analysis['success']:
            print(f"✅ ({analysis['rows']:,} rows, {analysis['columns']} columns)")
        else:
            print(f"❌ Error: {analysis['error']}")
    
    print("")
    
    # Generate report
    output_file = data_dir / 'dataset_summary.txt'
    print(f"📝 Generating summary report...")
    report_text = generate_report(analyses, output_file)
    
    print(f"✅ Report saved to: {output_file}")
    print("")
    
    # Print summary to console
    print("=" * 80)
    print("QUICK SUMMARY")
    print("=" * 80)
    
    successful = [a for a in analyses if a['success']]
    for analysis in successful:
        print(f"\n📄 {analysis['filename']}")
        print(f"   Rows: {analysis['rows']:,} | Columns: {analysis['columns']} | Size: {analysis['size']}")
        
        identified = analysis['identified_columns']
        if any(identified.values()):
            print(f"   Identified columns:")
            if identified['company_name']:
                print(f"     • Company: {identified['company_name']}")
            if identified['esg_score']:
                print(f"     • ESG Score: {identified['esg_score']}")
            if identified['industry']:
                print(f"     • Industry: {identified['industry']}")
            if identified['date']:
                print(f"     • Date: {identified['date']}")
    
    print("\n" + "=" * 80)
    print(f"✅ Complete! Full report saved to: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
