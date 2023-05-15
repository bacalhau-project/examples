import csv
import os
import shutil
import unittest
from random import choice

import pandas as pd
from fastavro import is_avro, reader
from src.converter import AvroConverter


class TestAvroConverter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.mkdir('tmp')
        usernames = ['Alex', 'Ivan', 'Natan', 'Lisa', 'Nika']
        cls.file_paths = {
            'csv': 'tmp/user_orders.csv',
            'result': 'tmp/user_orders.avro',
        }
        cls.num_rows = 101000
        with open(cls.file_paths['csv'], 'w') as f:
            writer = csv.writer(f, delimiter=',')
            column_names = ['id', 'user', 'cart']
            writer.writerow(column_names)
            for i in range(cls.num_rows):
                row = [i, choice(usernames), i]
                writer.writerow(row)
        cls.converter = AvroConverter(
            cls.file_paths['csv'],
            cls.file_paths['result'],
        )

    def test_convert_to_avro(self):
        TestAvroConverter.converter.convert()
        self.assertTrue(
            os.path.isfile(TestAvroConverter.file_paths['result']),
            'Avro result file does not exist'
        )
        self.assertTrue(
            is_avro(TestAvroConverter.file_paths['result']),
            'Type of the result file is not avro'
        )
        csv_df = pd.read_csv(TestAvroConverter.file_paths['csv'])
        with open(TestAvroConverter.file_paths['result'], 'rb') as f:
            avro_reader = reader(f)
            records = [record for record in avro_reader]
            avro_df = pd.DataFrame.from_records(records)
        self.assertTrue(
            csv_df.compare(avro_df).empty,
            'Invalid content of the result file'
        )

    @classmethod
    def tearDownClass(self):
        shutil.rmtree('tmp', ignore_errors=True)
        super().tearDownClass()
