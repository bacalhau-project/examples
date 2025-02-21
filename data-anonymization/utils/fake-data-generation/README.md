# Fake Data Generation Scripts

This directory contains Python scripts for generating synthetic sensitive data in both structured and unstructured formats. These scripts are designed to create realistic-looking test data for Bacalhau jobs while avoiding the use of actual sensitive information.

## 1. Structured Data Generation (structured_data_generation.py)

### Description:
This script generates structured sensitive data in CSV format, simulating a typical customer or employee database.

### Generated Data Fields:
- First Name
- Last Name
- Age (18-90)
- Social Security Number (SSN)
- ZIP Code
- City
- Country (United States)
- Credit Card Number

### Output:
- Creates a single CSV file named fake_sensitive_data_[timestamp].csv
- Default generation of 1000 records
- File naming format: fake_sensitive_data_YYYYMMDD_HHMMSS.csv

### Usage:
python structured_data_generation.py

## 2. Unstructured Data Generation (unstructured_data_generation.py)

### Description:
This script generates unstructured sensitive data in the form of internal memos and reports, simulating various business documents containing sensitive information.

### Generated Memo Types:
- Account Reviews
- Security Incident Reports
- Employee Updates
- Client Data Updates
- Compliance Reviews
- System Access Reports
- Data Privacy Alerts
- Customer Service Updates
- Internal Audit Findings
- Risk Assessment Reports

### Memo Content Includes:
- Headers with department and priority information
- Realistic timestamps and reference numbers
- Employee names and positions
- Email addresses
- Financial information (account numbers, transactions)
- Personal information (SSNs, credit card numbers)
- IP addresses and security incidents
- Compliance and audit findings

### Output:
- Creates multiple text files in a generated-memos subdirectory
- Default generation of 100 memos
- Files named sequentially as memo_1.txt, memo_2.txt, etc.
- Each memo is 2-5 pages long with multiple sections

### Usage:
python unstructured_data_generation.py

## Dependencies:
Both scripts require:
- Python 3.x
- Faker library (install with: pip install faker)

## Note:
The generated data is synthetic and designed for testing purposes only. While it looks realistic, it does not contain any actual sensitive information. The data format and content are suitable for testing data processing, privacy protection, and security-related Bacalhau jobs. 