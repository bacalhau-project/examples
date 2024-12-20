# PII Anonymization Case Study

Anonymize and Process your Sensitive Data with Bacalhau!  

## Setup and Usage

To get started with the code and datasets in this repository, follow these steps:

1. **Clone the Repository**

2. **Install Dependencies**

   Make sure you have the necessary dependencies installed. You can find the list of required libraries in the `requirements.txt` file (for Python).

   ```bash
   pip install -r requirements.txt
   ```
    **Note**: The scripts utilize AWS credentials in your environment.

3. **Run the Scripts**

   There are two executable scripts that create and delete AWS resources, with Boto3 created in this example. Navigate to the repo directory and execute the scripts directly with Python to anonymize the datasets. For example:

   ```bash
   python createinstance.py
   ```

## Files Description

- `sampledata.csv`: Sample dataset used for demonstration purposes.
- `cleanpii.py`: Python script for applying anonymization techniques.
- `createinstance.py`: Python script for creating AWS resources.
- `terminateinstances.py`: Python script for deleting AWS resources.
