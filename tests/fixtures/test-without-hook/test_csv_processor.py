#!/usr/bin/env python3
"""
Unit tests for CSV Processor
"""

import unittest
import os
import tempfile
from csv_processor import CSVProcessor


class TestCSVProcessor(unittest.TestCase):
    """Test cases for CSVProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files."""
        # Clean up any files created in temp directory
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)

    def test_read_csv_success(self):
        """Test successful CSV reading."""
        # Create a test CSV file
        test_file = os.path.join(self.temp_dir, 'test.csv')
        with open(test_file, 'w') as f:
            f.write('name,price,quantity\n')
            f.write('Product A,10.00,100\n')
            f.write('Product B,20.00,200\n')

        processor = CSVProcessor(test_file)
        processor.read_csv()

        self.assertEqual(len(processor.data), 2)
        self.assertEqual(processor.headers, ['name', 'price', 'quantity'])
        self.assertEqual(processor.data[0]['name'], 'Product A')

    def test_read_csv_file_not_found(self):
        """Test error handling for missing file."""
        processor = CSVProcessor('nonexistent_file.csv')

        with self.assertRaises(FileNotFoundError) as context:
            processor.read_csv()

        self.assertIn('not found', str(context.exception))

    def test_calculate_averages_numeric_columns(self):
        """Test average calculation for numeric columns."""
        test_file = os.path.join(self.temp_dir, 'test.csv')
        with open(test_file, 'w') as f:
            f.write('name,price,quantity\n')
            f.write('Product A,10.00,100\n')
            f.write('Product B,20.00,200\n')
            f.write('Product C,30.00,300\n')

        processor = CSVProcessor(test_file)
        processor.read_csv()
        averages = processor.calculate_averages()

        # Average of 10, 20, 30 = 20
        self.assertAlmostEqual(averages['price'], 20.00, places=2)
        # Average of 100, 200, 300 = 200
        self.assertAlmostEqual(averages['quantity'], 200.00, places=2)
        # Non-numeric column should not appear
        self.assertNotIn('name', averages)

    def test_calculate_averages_mixed_data(self):
        """Test average calculation with mixed numeric/non-numeric data."""
        test_file = os.path.join(self.temp_dir, 'test.csv')
        with open(test_file, 'w') as f:
            f.write('name,price,quantity\n')
            f.write('Product A,10.00,100\n')
            f.write('Product B,invalid,200\n')
            f.write('Product C,30.00,300\n')

        processor = CSVProcessor(test_file)
        processor.read_csv()
        averages = processor.calculate_averages()

        # Average of 10 and 30 (skipping 'invalid') = 20
        self.assertAlmostEqual(averages['price'], 20.00, places=2)
        # All quantity values are numeric
        self.assertAlmostEqual(averages['quantity'], 200.00, places=2)

    def test_write_summary(self):
        """Test writing summary to CSV file."""
        test_file = os.path.join(self.temp_dir, 'test.csv')
        summary_file = os.path.join(self.temp_dir, 'summary.csv')

        with open(test_file, 'w') as f:
            f.write('name,price,quantity\n')
            f.write('Product A,10.00,100\n')
            f.write('Product B,20.00,200\n')

        processor = CSVProcessor(test_file)
        processor.read_csv()
        averages = processor.calculate_averages()
        processor.write_summary(summary_file, averages)

        # Verify summary file was created and contains correct data
        self.assertTrue(os.path.exists(summary_file))

        with open(summary_file, 'r') as f:
            lines = f.readlines()
            self.assertEqual(lines[0].strip(), 'column,average')
            self.assertIn('price,15.00', lines[1])
            self.assertIn('quantity,150.00', lines[2])

    def test_process_end_to_end(self):
        """Test complete processing workflow."""
        test_file = os.path.join(self.temp_dir, 'test.csv')
        summary_file = os.path.join(self.temp_dir, 'summary.csv')

        with open(test_file, 'w') as f:
            f.write('name,price,quantity\n')
            f.write('Product A,10.00,100\n')
            f.write('Product B,20.00,200\n')

        processor = CSVProcessor(test_file)
        averages = processor.process(summary_file)

        # Verify averages returned
        self.assertAlmostEqual(averages['price'], 15.00, places=2)
        self.assertAlmostEqual(averages['quantity'], 150.00, places=2)

        # Verify summary file created
        self.assertTrue(os.path.exists(summary_file))

    def test_empty_csv_file(self):
        """Test error handling for empty CSV file."""
        test_file = os.path.join(self.temp_dir, 'empty.csv')
        with open(test_file, 'w') as f:
            f.write('name,price,quantity\n')  # Headers only, no data

        processor = CSVProcessor(test_file)

        with self.assertRaises(ValueError) as context:
            processor.read_csv()

        self.assertIn('no data rows', str(context.exception))


if __name__ == '__main__':
    unittest.main()
