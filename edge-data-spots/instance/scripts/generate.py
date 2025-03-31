import os
import random
import string

# Directory to store files
output_dir = "/mnt/data"
os.makedirs(output_dir, exist_ok=True)

# Number of files to generate
num_files = 1000

# File size range in bytes (change as needed)
min_size = 5000 * 1024
max_size = 20000 * 1024

for i in range(num_files):
    file_size = random.randint(min_size, max_size)  # Random size
    filename = os.path.join(output_dir, f"file_{i+1}.txt")

    # Generate random content
    content = ''.join(random.choices(string.ascii_letters + string.digits, k=file_size))

    # Write to file
    with open(filename, "w") as f:
        f.write(content)

    print(f"Generated: {filename} ({file_size} bytes)")

print(f"\n✅ Successfully generated {num_files} random text files in '{output_dir}'")