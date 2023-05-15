import csv
import os
import shutil
import unittest
from random import choice

import pandas as pd
from src.converter import ParquetConverter


class TestParquetConverter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.mkdir('tmp')
        usernames = ['Alex', 'Ivan', 'Natan', 'Lisa', 'Nika']
        cls.file_paths = {
            'csv': 'tmp/user_orders.csv',
            'result': 'tmp/user_orders.parquet',
        }
        cls.num_rows = 101000
        with open(cls.file_paths['csv'], 'w') as f:
            writer = csv.writer(f, delimiter=',')
            column_names = ['id', 'user', 'cart']
            writer.writerow(column_names)
            for i in range(cls.num_rows):
                row = [i, choice(usernames), i]
                writer.writerow(row)
        cls.converter = ParquetConverter(
            cls.file_paths['csv'],
            cls.file_paths['result'],
        )

    def test_convert_to_parquet(self):
        TestParquetConverter.converter.convert()
        self.assertTrue(
            os.path.isfile(TestParquetConverter.file_paths['result']),
            'Parquet result file does not exist'
        )
        csv_df = pd.read_csv(TestParquetConverter.file_paths['csv'])
        parquet_df = pd.read_parquet(TestParquetConverter.file_paths['result'])
        self.assertTrue(
            csv_df.compare(parquet_df).empty,
            'Invalid content of the result file'
        )

    @classmethod
    def tearDownClass(self):
        shutil.rmtree('tmp', ignore_errors=True)
        super().tearDownClass()
