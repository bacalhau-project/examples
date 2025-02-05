# ARX Data Anonymization Examples

This directory contains three Java classes that demonstrate different approaches to data anonymization using the ARX library. Each class implements various privacy-preserving techniques for structured data.

## ARXTest1.java

### Purpose:
Demonstrates basic k-anonymity and l-diversity implementation with hierarchical data generalization.

### Features:
- Implements k-anonymity (k=4) and distinct l-diversity
- Uses interval-based hierarchy for age anonymization
- Uses redaction-based hierarchy for ZIP code anonymization
- Handles sensitive attributes (disease field)
- Includes detailed statistics output

### Key Components:
- Age intervals: 0-30, 30-40, 40-100
- Right-to-left ZIP code redaction
- 20% suppression limit
- Prints both original and anonymized data

## ARXTest2.java

### Purpose:
Focuses on handling personally identifiable information (PII) with efficient data writing capabilities.

### Features:
- Implements k-anonymity (k=3)
- More granular age intervals
- Efficient CSV output writing
- Handles multiple identifying attributes

### Key Components:
- Age intervals: 0-30, 30-50, 50-70, 70-100
- Identifies and handles multiple PII fields:
  - First name
  - Last name
  - SSN
  - Credit card number
  - City
- Writes output to data-generator/anonymized_output.csv
- Uses buffered writing for better performance

## ARXTest3.java

### Purpose:
Implements custom hierarchical anonymization with entropy-based optimization.

### Features:
- Uses custom hierarchical generalization
- Implements k-anonymity (k=3)
- Uses entropy metric for optimization
- Dynamic ZIP code hierarchy generation

### Key Components:
- Custom age hierarchy with three levels:
  - Exact age
  - 10-year ranges
  - Complete generalization
- Dynamic ZIP code hierarchy with four levels:
  - Full ZIP code
  - 3 digits + **
  - 2 digits + ***
  - Complete masking (*****)
- Lower suppression limit (4%)
- Outputs to data-generator/anonymized_output_test3.csv

## Common Features Across All Classes:
- CSV input/output handling
- Detailed transformation statistics
- Suppression rate calculation
- Equivalence class statistics
- Privacy model implementation

## Usage Notes:
1. All classes expect a CSV input file named some.csv
2. Input CSV should contain appropriate columns as defined in each class
3. Output files are generated in the data-generator directory
4. Statistics are printed to standard output

## Dependencies:
- ARX Data Anonymization Tool
- Java Standard Library
- CSV handling capabilities 