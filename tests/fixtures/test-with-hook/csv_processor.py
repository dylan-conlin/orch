#!/usr/bin/env python3
"""
CSV Processor - Reads CSV files and calculates column averages for numeric columns.
"""

import csv
import sys
from pathlib import Path
from typing import Dict, List, Any


def read_csv(file_path: str) -> tuple[List[str], List[Dict[str, Any]]]:
    """
    Read a CSV file and return headers and rows.

    Args:
        file_path: Path to the CSV file

    Returns:
        Tuple of (headers, rows) where rows is a list of dictionaries

    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        ValueError: If the CSV file is empty or malformed
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        if not headers:
            raise ValueError(f"CSV file is empty or has no headers: {file_path}")

        rows = list(reader)

        if not rows:
            raise ValueError(f"CSV file has no data rows: {file_path}")

    return headers, rows


def calculate_averages(headers: List[str], rows: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate averages for numeric columns.

    Args:
        headers: List of column headers
        rows: List of row dictionaries

    Returns:
        Dictionary mapping column name to average value
    """
    averages = {}

    for column in headers:
        numeric_values = []

        for row in rows:
            value = row.get(column, '').strip()

            # Try to convert to float
            try:
                numeric_values.append(float(value))
            except (ValueError, TypeError):
                # Skip non-numeric values
                continue

        # Calculate average if we found numeric values
        if numeric_values:
            averages[column] = sum(numeric_values) / len(numeric_values)

    return averages


def write_summary(output_path: str, averages: Dict[str, float]) -> None:
    """
    Write the averages summary to a CSV file.

    Args:
        output_path: Path to the output CSV file
        averages: Dictionary of column averages
    """
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['column', 'average'])

        for column, avg in averages.items():
            writer.writerow([column, f'{avg:.2f}'])


def process_csv(input_path: str, output_path: str = 'summary.csv') -> Dict[str, float]:
    """
    Main processing function: reads CSV, calculates averages, writes summary.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output summary CSV file (default: summary.csv)

    Returns:
        Dictionary of calculated averages

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If input file is invalid
    """
    try:
        # Read the CSV file
        headers, rows = read_csv(input_path)

        # Calculate averages for numeric columns
        averages = calculate_averages(headers, rows)

        # Write summary
        write_summary(output_path, averages)

        return averages

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: python csv_processor.py <input_csv> [output_csv]")
        print("Example: python csv_processor.py products.csv summary.csv")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'summary.csv'

    try:
        averages = process_csv(input_path, output_path)

        print(f"Processed {input_path}")
        print(f"Summary written to {output_path}")
        print("\nColumn averages:")
        for column, avg in averages.items():
            print(f"  {column}: {avg:.2f}")

    except (FileNotFoundError, ValueError) as e:
        sys.exit(1)


if __name__ == '__main__':
    main()
