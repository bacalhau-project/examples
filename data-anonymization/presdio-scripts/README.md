# Microsoft Presidio Text Anonymization

This directory contains a Python script that implements batch text anonymization using Microsoft's Presidio privacy SDK. The script is designed to process multiple text files and automatically detect and anonymize sensitive information.

## Script Overview: presdio_anonymizer.py

### Purpose
The script provides automated detection and anonymization of sensitive data in text files using Microsoft Presidio's analyzer and anonymizer engines.

### Key Features
- Batch processing of text files
- Recursive directory scanning
- Detailed logging system
- Progress tracking
- Error handling and reporting

### Supported Entity Types
The script detects and anonymizes multiple types of sensitive information:
- Personal Names
- Phone Numbers
- Email Addresses
- Credit Card Numbers
- Cryptocurrency Addresses
- IP Addresses
- US Social Security Numbers (SSN)
- US Individual Taxpayer ID (ITIN)
- US Passport Numbers
- IBAN Codes
- US Driver License Numbers
- Location Information
- Date and Time
- NRP
- US Bank Numbers
- Medical License Numbers

## How It Works

### Directory Structure
- Input Directory: generated-memos
- Output Directory: anonymized-memos
- Logs Directory: logs

### Process Flow
1. Initializes Presidio analyzer and anonymizer engines
2. Scans input directory for text files
3. For each file:
   - Reads the content
   - Analyzes for sensitive information
   - Applies anonymization
   - Saves to output directory
4. Maintains original directory structure
5. Generates detailed logs

### Logging Features
- Timestamp-based log files
- Progress tracking every 100 files
- Error reporting and handling
- Success confirmations
- Processing statistics

## Usage

### Prerequisites
- Microsoft Presidio Analyzer
- Microsoft Presidio Anonymizer
- Python 3.x

### Running the Script
1. Place text files in the generated-memos directory
2. Run the script
3. Find anonymized files in anonymized-memos directory
4. Check logs directory for processing details

### Output
- Maintains original file structure
- Creates anonymized versions of all text files
- Generates detailed log files

## Error Handling
- Catches and logs file processing errors
- Continues processing remaining files
- Records detailed error information
- Maintains processing statistics

## Performance
- Processes files in batch
- Progress tracking for large directories
- Efficient file handling with proper encoding
- Structured logging for monitoring

## Notes
- Designed for text files (.txt)
- Preserves original file structure
- Creates necessary directories automatically
- Handles UTF-8 encoded files 