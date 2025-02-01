from faker import Faker
import os
import random


class MemoGenerator:
    def __init__(self):
        self.fake = Faker()
        self.memo_types = [
            "Account Review",
            "Security Incident Report",
            "Employee Update",
            "Client Data Update",
            "Compliance Review",
            "System Access Report",
            "Data Privacy Alert",
            "Customer Service Update",
            "Internal Audit Findings",
            "Risk Assessment Report"
        ]

    def create_memo_header(self):
        memo_type = random.choice(self.memo_types)
        department = random.choice(['IT', 'HR', 'Finance', 'Compliance', 'Operations', 'Legal'])
        priority = random.choice(['URGENT', 'CONFIDENTIAL', 'ROUTINE', 'PRIORITY'])

        return f"""
{priority}
{department} MEMORANDUM
Reference: {self.fake.uuid4()}

Date: {self.fake.date()}
Time: {self.fake.time()}
From: {self.fake.name()}, {self.fake.job()}
Email: {self.fake.company_email()}
To: {self.fake.name()}, {self.fake.job()}
CC: {self.fake.name()}, {self.fake.name()}
Subject: {memo_type} - {self.fake.catch_phrase()}

"""

    def create_intro_paragraph(self):
        intros = [
            f"I am writing to bring to your attention a matter concerning {self.fake.name()}'s account.",
            f"This memo serves as a formal documentation of recent activities detected in our systems.",
            f"Please review the following information regarding customer activity from IP {self.fake.ipv4()}.",
            f"As part of our ongoing compliance review, we have identified several items requiring immediate attention.",
            f"This document contains sensitive updates about recent transactions and account modifications."
        ]
        return random.choice(intros) + "\n\n"

    def create_memo_section(self):
        templates = [
            # Financial Templates
            f"""Our financial review identified unusual transactions for account holder {self.fake.name()} 
(SSN: {self.fake.ssn()}). Multiple charges totaling ${self.fake.random_number(5)} were processed through 
card {self.fake.credit_card_number()} between {self.fake.date()} and {self.fake.date()}. The transactions 
originated from IP address {self.fake.ipv4()}.
""",

            # Customer Service Templates
            f"""Customer {self.fake.name()} (ID: {self.fake.uuid4()}) reported unauthorized access 
to their account. Their registered email {self.fake.email()} showed login attempts from multiple 
locations. The primary IBAN {self.fake.iban()} has been temporarily frozen pending investigation.
""",

            # Employee Records Templates
            f"""Please update the following employee information in our secure database:
- Name: {self.fake.name()}
- Employee ID: {self.fake.random_number(6)}
- Department: {random.choice(['IT', 'HR', 'Finance', 'Sales'])}
- New Email: {self.fake.company_email()}
- Direct Deposit: {self.fake.iban()}
- Office Location: {self.fake.city()}, {self.fake.state()}
""",

            # Security Incident Templates
            f"""Security Alert [{self.fake.date()}]: Multiple failed authentication attempts detected
Source IP: {self.fake.ipv4()}
Target Account: {self.fake.name()}
Account Number: {self.fake.bban()}
Timestamp Range: {self.fake.date()} {self.fake.time()} to {self.fake.date()} {self.fake.time()}
""",

            # Compliance Templates
            f"""During routine compliance checking, the following irregularities were noted:
1. Account {self.fake.iban()} showed unusual patterns
2. User {self.fake.name()} accessed system from unregistered IP {self.fake.ipv4()}
3. Credit card {self.fake.credit_card_number()} triggered our fraud detection system
""",

            # Data Privacy Templates
            f"""Privacy Impact Assessment Results:
Individual: {self.fake.name()}
Assessed Data: SSN ({self.fake.ssn()}), Payment Methods ({self.fake.credit_card_number()})
Risk Level: {random.choice(['High', 'Medium', 'Low'])}
Mitigation Status: {random.choice(['Pending', 'In Progress', 'Completed'])}
""",

            # Audit Templates
            f"""Internal audit findings for {self.fake.date()}:
Auditor: {self.fake.name()}
Subject Account: {self.fake.iban()}
Location: {self.fake.city()}, {self.fake.state()}
IP Range: {self.fake.ipv4()} to {self.fake.ipv4()}
Finding Level: {random.choice(['Critical', 'Major', 'Minor'])}
"""
        ]
        return random.choice(templates)

    def create_footer(self):
        classifications = [
            "CONFIDENTIAL - INTERNAL USE ONLY",
            "RESTRICTED - HANDLE WITH CARE",
            "SENSITIVE INFORMATION ENCLOSED",
            "PRIVACY LEVEL 1 - STRICTLY CONFIDENTIAL"
        ]

        return f"""\n{'=' * 50}
{random.choice(classifications)}

Distribution: Limited
Generated: {self.fake.date()} {self.fake.time()}
Document ID: {self.fake.uuid4()}

For questions contact:
{self.fake.name()}
Compliance Officer
{self.fake.company_email()}
Internal Extension: {random.randint(1000, 9999)}
"""

    def generate_memo(self, filename, min_pages=2, max_pages=5):
        os.makedirs("generated-memos", exist_ok=True)
        filepath = os.path.join("generated-memos", filename)

        num_pages = random.randint(min_pages, max_pages)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.create_memo_header())
            f.write(self.create_intro_paragraph())

            for page in range(num_pages):
                f.write(f"\nPage {page + 1} of {num_pages}\n{'=' * 50}\n\n")

                # Variable number of paragraphs per page
                num_paragraphs = random.randint(2, 4)
                for _ in range(num_paragraphs):
                    f.write(self.create_memo_section())
                    f.write("\n\n")

                if page < num_pages - 1:
                    f.write(f"\n{'- ' * 25}\n")

            f.write(self.create_footer())


def main():
    generator = MemoGenerator()
    num_memos = 100  # Change this to generate more or fewer memos

    for i in range(num_memos):
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memo_{i + 1}.txt"
        generator.generate_memo(filename)
        print(f"Generated memo: {filename}")


if __name__ == "__main__":
    main()