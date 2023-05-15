# CSV convertor to avro/parquet

## Description:
[converter.py](src/converter.py) contains converter classes that convert received csv file to file with chosen extension.  
To run the convertation call the converter module with fallowing parameters:
- path to csv file;
- path to result file;
- extension.
Available extension: avro, parquet.  
Csv file is read and convert as a stream to avoid running out of memory limit.

## Installation:
Install requirements with poetry:
```shell
poetry install
```
Alternatively virtual environment could be created through venv module:
```shell
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```
Run tests:
```shell
python -m unittest
```

## Usage:
```shell
python converter.py <path_to_csv> <path_to_result_file> <extension>
```