#!/usr/bin/env python3
"""
CSV Processor - Reads CSV files and calculates column averages for numeric columns.
"""

import csv
from typing import Dict, List, Any


class CSVProcessor:
    """Processes CSV files and calculates statistics."""

    def __init__(self, input_file: str):
        """Initialize the processor with an input file path."""
        self.input_file = input_file
        self.data: List[Dict[str, Any]] = []
        self.headers: List[str] = []

    def read_csv(self) -> None:
        """Read CSV file and store data.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            ValueError: If the CSV file is empty or malformed.
        """
        try:
            with open(self.input_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.headers = reader.fieldnames

                if not self.headers:
                    raise ValueError("CSV file has no headers")

                self.data = list(reader)

                if not self.data:
                    raise ValueError("CSV file has no data rows")

        except FileNotFoundError:
            raise FileNotFoundError(f"Input file '{self.input_file}' not found")
        except csv.Error as e:
            raise ValueError(f"Error reading CSV file: {e}")

    def calculate_averages(self) -> Dict[str, float]:
        """Calculate averages for numeric columns.

        Returns:
            Dictionary mapping column names to their average values.
            Non-numeric columns are skipped.
        """
        if not self.data:
            return {}

        averages = {}

        for header in self.headers:
            numeric_values = []

            for row in self.data:
                try:
                    value = float(row[header])
                    numeric_values.append(value)
                except (ValueError, TypeError):
                    # Skip non-numeric values
                    continue

            if numeric_values:
                averages[header] = sum(numeric_values) / len(numeric_values)

        return averages

    def write_summary(self, output_file: str, averages: Dict[str, float]) -> None:
        """Write summary statistics to a CSV file.

        Args:
            output_file: Path to the output CSV file.
            averages: Dictionary of column averages to write.
        """
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['column', 'average'])

            for column, avg in averages.items():
                writer.writerow([column, f'{avg:.2f}'])

    def process(self, output_file: str = 'summary.csv') -> Dict[str, float]:
        """Process the CSV file and generate summary.

        Args:
            output_file: Path to the output summary file.

        Returns:
            Dictionary of calculated averages.
        """
        self.read_csv()
        averages = self.calculate_averages()
        self.write_summary(output_file, averages)
        return averages


def main():
    """Main entry point for the CSV processor."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python csv_processor.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'summary.csv'

    try:
        processor = CSVProcessor(input_file)
        averages = processor.process(output_file)

        print(f"Successfully processed {input_file}")
        print(f"Summary written to {output_file}")
        print("\nColumn Averages:")
        for column, avg in averages.items():
            print(f"  {column}: {avg:.2f}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
