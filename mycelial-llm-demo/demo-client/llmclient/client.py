from datetime import datetime, timedelta
import hashlib
import readline
import time

from .config import Config
from .database import get_answers_db, get_questions_db

from boxing import boxing
from halo import Halo


def display_answer(answer=None, spinner=None):
    if answer:
        if spinner:
            spinner.succeed("Query successful")
        print("")
        print(answer.message)
    else:
        if spinner:
            spinner.fail("Query took too long")
        print("")


def run(cfg: Config):
    questions, Question = get_questions_db(cfg.questions)
    answers, Answer = get_answers_db(cfg.answers)

    while True:
        message = input("> ")
        if message.lower() == ".q":
            break
        elif message.strip() == "":
            continue

        key = hashlib.md5(message.encode("utf-8")).hexdigest()

        # Check for existing answer
        result = Answer.get(key=key)
        if result is not None:
            display_answer(result, None)
            continue

        q = Question(key=key, message=message)
        questions.commit()

        # Start a spinner and then keep querying the answers table
        # until our key turns up.  We should probably timeout after
        # some reasonable time period.
        spinner = Halo(text="Waiting", spinner="dots")
        spinner.start()

        ## wait for key to turn up in answers table
        finish_before = datetime.now() + timedelta(seconds=cfg.timeout)

        while result is None:
            result = Answer.get(key=key)
            if result or datetime.now() > finish_before:
                break

            time.sleep(0.25)

        display_answer(result, spinner)
