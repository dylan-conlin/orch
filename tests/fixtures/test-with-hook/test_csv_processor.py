#!/usr/bin/env python3
"""
Unit tests for CSV Processor
"""

import unittest
import tempfile
import os
from pathlib import Path
from csv_processor import read_csv, calculate_averages, write_summary, process_csv


class TestCSVProcessor(unittest.TestCase):
    """Test suite for CSV processor functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_temp_csv(self, filename: str, content: str) -> str:
        """Helper to create a temporary CSV file."""
        path = os.path.join(self.temp_dir, filename)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def test_read_csv_success(self):
        """Test reading a valid CSV file."""
        csv_content = """name,price,quantity
Widget,10.50,100
Gadget,25.00,50
Tool,15.75,75"""

        csv_path = self.create_temp_csv('test.csv', csv_content)
        headers, rows = read_csv(csv_path)

        self.assertEqual(headers, ['name', 'price', 'quantity'])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['name'], 'Widget')
        self.assertEqual(rows[0]['price'], '10.50')
        self.assertEqual(rows[0]['quantity'], '100')

    def test_read_csv_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        with self.assertRaises(FileNotFoundError):
            read_csv('nonexistent.csv')

    def test_read_csv_empty_file(self):
        """Test that ValueError is raised for empty CSV files."""
        csv_path = self.create_temp_csv('empty.csv', '')

        with self.assertRaises(ValueError) as context:
            read_csv(csv_path)

        self.assertIn('empty', str(context.exception).lower())

    def test_read_csv_no_data_rows(self):
        """Test that ValueError is raised for CSV with headers but no data."""
        csv_path = self.create_temp_csv('headers_only.csv', 'name,price,quantity\n')

        with self.assertRaises(ValueError) as context:
            read_csv(csv_path)

        self.assertIn('no data rows', str(context.exception).lower())

    def test_calculate_averages_numeric_columns(self):
        """Test calculating averages for numeric columns."""
        headers = ['name', 'price', 'quantity']
        rows = [
            {'name': 'Widget', 'price': '10.50', 'quantity': '100'},
            {'name': 'Gadget', 'price': '25.00', 'quantity': '50'},
            {'name': 'Tool', 'price': '15.75', 'quantity': '75'}
        ]

        averages = calculate_averages(headers, rows)

        # name column should be excluded (not numeric)
        self.assertNotIn('name', averages)

        # Check numeric columns
        self.assertIn('price', averages)
        self.assertIn('quantity', averages)

        # Check average values
        self.assertAlmostEqual(averages['price'], 17.083333, places=2)
        self.assertAlmostEqual(averages['quantity'], 75.0, places=2)

    def test_calculate_averages_mixed_data(self):
        """Test calculating averages with mixed numeric/non-numeric data."""
        headers = ['name', 'price', 'quantity']
        rows = [
            {'name': 'Widget', 'price': '10.50', 'quantity': '100'},
            {'name': 'Gadget', 'price': 'N/A', 'quantity': '50'},
            {'name': 'Tool', 'price': '15.75', 'quantity': 'out of stock'}
        ]

        averages = calculate_averages(headers, rows)

        # Price average should only include numeric values
        self.assertAlmostEqual(averages['price'], 13.125, places=2)

        # Quantity average should only include numeric values
        self.assertAlmostEqual(averages['quantity'], 75.0, places=2)

    def test_write_summary(self):
        """Test writing summary to CSV file."""
        output_path = os.path.join(self.temp_dir, 'summary.csv')
        averages = {
            'price': 17.083333,
            'quantity': 75.0
        }

        write_summary(output_path, averages)

        # Verify file was created
        self.assertTrue(os.path.exists(output_path))

        # Verify content
        with open(output_path, 'r') as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 3)  # Header + 2 data rows
        self.assertIn('column,average', lines[0])
        self.assertIn('price,17.08', lines[1])
        self.assertIn('quantity,75.00', lines[2])

    def test_process_csv_end_to_end(self):
        """Test complete CSV processing workflow."""
        # Create input CSV
        csv_content = """name,price,quantity
Widget,10.50,100
Gadget,25.00,50
Tool,15.75,75"""

        input_path = self.create_temp_csv('products.csv', csv_content)
        output_path = os.path.join(self.temp_dir, 'summary.csv')

        # Process
        averages = process_csv(input_path, output_path)

        # Verify averages
        self.assertIn('price', averages)
        self.assertIn('quantity', averages)
        self.assertAlmostEqual(averages['price'], 17.083333, places=2)
        self.assertAlmostEqual(averages['quantity'], 75.0, places=2)

        # Verify output file exists
        self.assertTrue(os.path.exists(output_path))

    def test_process_csv_missing_file_error(self):
        """Test error handling for missing input file."""
        with self.assertRaises(FileNotFoundError):
            process_csv('nonexistent.csv')


if __name__ == '__main__':
    unittest.main()
