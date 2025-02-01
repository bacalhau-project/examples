from faker import Faker
import csv
from datetime import datetime
import random


def generate_fake_data(filename, num_records=10):
    # Initialize Faker with US locale for consistent data format
    fake = Faker('en_US')

    # Define headers for the CSV file
    headers = ['first_name', 'last_name', 'age', 'ssn', 'zip_code',
               'city', 'country', 'credit_card_number']

    # Open file and write data directly to disk
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        # Generate and write records one by one
        for _ in range(num_records):
            record = {
                'first_name': fake.first_name(),
                'last_name': fake.last_name(),
                'age': random.randint(18, 90),
                'ssn': fake.ssn(),
                'zip_code': fake.zipcode(),
                'city': fake.city(),
                'country': 'United States',  # Since we're using US locale
                'credit_card_number': fake.credit_card_number()
            }
            writer.writerow(record)


if __name__ == "__main__":
    # Generate the filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fake_sensitive_data_{timestamp}.csv"

    # Generate 1000 records (you can modify this number)
    generate_fake_data(filename, num_records=1000)
    print(f"Generated fake data has been written to {filename}")