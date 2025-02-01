
from pathlib import Path
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from datetime import datetime
import logging


class BatchAnonymizer:
    def __init__(self, input_dir, output_dir):
        # Initialize Presidio engines
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

        # Setup input/output directories
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        # List of entities to detect
        self.entities = [
            "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD",
            "CRYPTO", "IP_ADDRESS", "US_SSN", "US_ITIN", "US_PASSPORT",
            "IBAN_CODE", "US_DRIVER_LICENSE", "LOCATION", "DATE_TIME",
            "NRP", "US_BANK_NUMBER", "MEDICAL_LICENSE"
        ]

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'logs/anonymization_{datetime.now():%Y%m%d_%H%M%S}.log'),
                logging.StreamHandler()
            ]
        )

    def process_file(self, input_file: Path):
        try:
            # Create corresponding output file path
            relative_path = input_file.relative_to(self.input_dir)
            output_file = self.output_dir / relative_path

            # Create output directory if it doesn't exist
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                text = f.read()

            # Analyze text
            analyzer_results = self.analyzer.analyze(
                text=text,
                entities=self.entities,
                language='en'
            )

            # Anonymize text
            anonymized_text = self.anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results
            ).text

            # Write anonymized text to output file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(anonymized_text)

            logging.info(f"Successfully processed: {relative_path}")

        except Exception as e:
            logging.error(f"Error processing {input_file}: {str(e)}")

    def process_directory(self):
        try:
            # Count total files for progress tracking
            total_files = sum(1 for _ in self.input_dir.rglob('*.txt'))
            processed_files = 0

            logging.info(f"Starting batch anonymization of {total_files} files")

            # Process each .txt file in the input directory and its subdirectories
            for file_path in self.input_dir.rglob('*.txt'):
                self.process_file(file_path)

                processed_files += 1
                if processed_files % 100 == 0:  # Log progress every 100 files
                    logging.info(f"Processed {processed_files}/{total_files} files")

            logging.info(f"Completed processing {processed_files} files")

        except Exception as e:
            logging.error(f"Error during batch processing: {str(e)}")


def main():
    # Define input and output directories
    input_directory = "generated-memos"  # Directory containing original files
    output_directory = "anonymized-memos"  # Directory for anonymized files

    # Create and run the batch anonymizer
    anonymizer = BatchAnonymizer(input_directory, output_directory)
    anonymizer.process_directory()


if __name__ == "__main__":
    main()