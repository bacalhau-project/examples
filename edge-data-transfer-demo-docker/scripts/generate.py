import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


output_dir = "/mnt/data"
num_files = 1000
min_size = 5000 * 1024
max_size = 20000 * 1024
num_workers = os.cpu_count() or 2

os.makedirs(output_dir, exist_ok=True)

def generate_file(file_index: int):
    """Generuje jeden losowy plik binarny."""
    file_size = random.randint(min_size, max_size)
    filename = Path(output_dir) / f"file_{file_index + 1}.bin"
    with open(filename, "wb") as f:
        f.write(os.urandom(file_size))
    return f"✅ Generated {filename.name} ({file_size} bytes)"

if __name__ == "__main__":
    print(f"🚀 Generating {num_files} files using {num_workers} workers...")
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        for result in executor.map(generate_file, range(num_files)):
            print(result)

    print(f"\n✅ Done. Files are stored in: {output_dir}")
