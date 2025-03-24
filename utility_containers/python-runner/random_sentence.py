import random
import time

words = [
    "cat",
    "dog",
    "apple",
    "sky",
    "river",
    "mountain",
    "run",
    "jumps",
    "eats",
    "beautiful",
    "quick",
    "fox",
]

try:
    while True:
        sentence = " ".join(random.choices(words, k=3)).capitalize() + "."
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {sentence}")
        time.sleep(1)
except KeyboardInterrupt:
    print("Process interrupted by user.")
