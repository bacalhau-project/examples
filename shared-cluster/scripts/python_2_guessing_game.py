# Random simulation function
import random
import string
from datetime import datetime

# Global variables
WORD_LIST = [
    "python",
    "programming",
    "computer",
    "algorithm",
    "database",
    "network",
    "security",
    "interface",
    "function",
    "variable",
]
DIFFICULTY_LEVELS = {"easy": 3, "medium": 5, "hard": 7}
MAX_ROUNDS = 10
current_score = 0
current_difficulty = "medium"
game_log = []


def generate_word():
    return random.choice(WORD_LIST)


def scramble_word(word):
    word_chars = list(word)
    random.shuffle(word_chars)
    return "".join(word_chars)


def simulate_guess(original_word, difficulty):
    # Simulate a guess based on difficulty
    if difficulty == "easy":
        chance_correct = 0.7
    elif difficulty == "medium":
        chance_correct = 0.5
    else:
        chance_correct = 0.3

    if random.random() < chance_correct:
        return original_word
    else:
        # Return a wrong guess by changing a random character
        wrong_guess = list(original_word)
        index = random.randint(0, len(wrong_guess) - 1)
        wrong_guess[index] = random.choice(string.ascii_lowercase)
        return "".join(wrong_guess)


def check_guess(original_word, simulated_guess):
    global current_score
    if simulated_guess == original_word:
        current_score += len(original_word)
        return True
    return False


def adjust_difficulty():
    global current_difficulty
    if current_score > 50:
        current_difficulty = "hard"
    elif current_score > 20:
        current_difficulty = "medium"
    else:
        current_difficulty = "easy"


def play_round(round_number):
    word = generate_word()
    scrambled = scramble_word(word)
    attempts = DIFFICULTY_LEVELS[current_difficulty]

    round_log = {
        "round": round_number,
        "word": word,
        "scrambled": scrambled,
        "difficulty": current_difficulty,
        "attempts": [],
        "success": False,
    }

    for i in range(attempts):
        guess = simulate_guess(word, current_difficulty)
        success = check_guess(word, guess)
        round_log["attempts"].append({"guess": guess, "correct": success})

        if success:
            round_log["success"] = True
            adjust_difficulty()
            break

    game_log.append(round_log)


def simulate_game_session():
    global current_score, current_difficulty

    start_time = datetime.now()
    for round_num in range(1, MAX_ROUNDS + 1):
        play_round(round_num)
    end_time = datetime.now()

    game_summary = {
        "total_rounds": MAX_ROUNDS,
        "final_score": current_score,
        "final_difficulty": current_difficulty,
        "duration": str(end_time - start_time),
        "rounds": game_log,
    }

    return game_summary


def display_game_summary(summary):
    print("=== Word Scramble Game Summary ===")
    print(f"Total Rounds: {summary['total_rounds']}")
    print(f"Final Score: {summary['final_score']}")
    print(f"Final Difficulty: {summary['final_difficulty']}")
    print(f"Game Duration: {summary['duration']}")
    print("\nRound Details:")
    for round_data in summary["rounds"]:
        print(f"\nRound {round_data['round']}:")
        print(f"  Word: {round_data['word']}")
        print(f"  Scrambled: {round_data['scrambled']}")
        print(f"  Difficulty: {round_data['difficulty']}")
        print(f"  Success: {round_data['success']}")
        print("  Attempts:")
        for attempt in round_data["attempts"]:
            print(f"    Guess: {attempt['guess']}, Correct: {attempt['correct']}")


def run_simulation():
    game_summary = simulate_game_session()
    display_game_summary(game_summary)


if __name__ == "__main__":
    run_simulation()
