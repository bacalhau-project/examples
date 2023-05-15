import os
import sys
from abc import ABCMeta, abstractmethod

import fastavro
import numpy as np
import pandas as pd
from pyarrow import Table, parquet


class BaseConverter(metaclass=ABCMeta):
    """
    Base class for converters.

    Validate received parameters for future use.
    """
    def __init__(
        self,
        csv_file_path: str,
        target_file_path: str,
    ) -> None:
        self.csv_file_path = csv_file_path
        self.target_file_path = target_file_path

    @property
    def csv_file_path(self):
        return self._csv_file_path

    @csv_file_path.setter
    def csv_file_path(self, path):
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        _, extension = os.path.splitext(path)
        if not os.path.isfile(path) or extension != '.csv':
            raise FileNotFoundError(
                f'No such csv file: {path}'
            )
        self._csv_file_path = path

    @property
    def target_file_path(self):
        return self._target_file_path

    @target_file_path.setter
    def target_file_path(self, path):
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        target_dir = os.path.dirname(path)
        if not os.path.isdir(target_dir):
            raise FileNotFoundError(
                f'No such directory: {target_dir}\n'
                'Choose existing or create directory for result file.'
            )
        if os.path.isfile(path):
            raise FileExistsError(
                f'File {path} has already exists.'
                'Usage of existing file may result in data loss.'
            )
        self._target_file_path = path

    def get_csv_reader(self):
        """Return csv reader which read csv file as a stream"""
        return pd.read_csv(
            self.csv_file_path,
            iterator=True,
            chunksize=100000
        )

    @abstractmethod
    def convert(self):
        """Should be implemented in child class"""
        pass


class ParquetConverter(BaseConverter):
    """
    Convert received csv file to parquet file.

    Take path to csv file and path to result file.
    """
    def convert(self):
        """Read csv file as a stream and write data to parquet file."""
        csv_reader = self.get_csv_reader()
        writer = None
        for chunk in csv_reader:
            if not writer:
                table = Table.from_pandas(chunk)
                writer = parquet.ParquetWriter(
                    self.target_file_path, table.schema
                )
            table = Table.from_pandas(chunk)
            writer.write_table(table)
        writer.close()


class AvroConverter(BaseConverter):
    """
    Convert received csv file to avro file.

    Take path to csv file and path to result file.
    """
    NUMPY_TO_AVRO_TYPES = {
        np.dtype('?'): 'boolean',
        np.dtype('int8'): 'int',
        np.dtype('int16'): 'int',
        np.dtype('int32'): 'int',
        np.dtype('uint8'): 'int',
        np.dtype('uint16'): 'int',
        np.dtype('uint32'): 'int',
        np.dtype('int64'): 'long',
        np.dtype('uint64'): 'long',
        np.dtype('O'): ['null', 'string', 'float'],
        np.dtype('unicode_'): 'string',
        np.dtype('float32'): 'float',
        np.dtype('float64'): 'double',
        np.dtype('datetime64'): {
            'type': 'long',
            'logicalType': 'timestamp-micros'
        },
    }

    def get_avro_schema(self, pandas_df):
        """Generate avro schema."""
        column_dtypes = pandas_df.dtypes
        schema_name = os.path.basename(self.target_file_path)
        schema = {
            'type': 'record',
            'name': schema_name,
            'fields': [
                {
                    'name': name,
                    'type': AvroConverter.NUMPY_TO_AVRO_TYPES[dtype]
                } for (name, dtype) in column_dtypes.items()
            ]
        }
        return fastavro.parse_schema(schema)

    def convert(self):
        """Read csv file as a stream and write data to avro file."""
        csv_reader = self.get_csv_reader()
        schema = None
        with open(self.target_file_path, 'a+b') as f:
            for chunk in csv_reader:
                if not schema:
                    schema = self.get_avro_schema(chunk)
                fastavro.writer(
                    f,
                    schema=schema,
                    records=chunk.to_dict('records')
                )


if __name__ == '__main__':
    converters = {
        'parquet': ParquetConverter,
        'avro': AvroConverter
    }
    csv_file, result_path, result_type = sys.argv[1], sys.argv[2], sys.argv[3]
    if result_type.lower() not in converters:
        raise ValueError(
            'Invalid target type. Avalible types: avro, parquet.'
        )
    converter = converters[result_type.lower()](csv_file, result_path)
    converter.convert()
