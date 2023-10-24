from datetime import datetime, timedelta
import hashlib
import time

from .config import Config
from .database import get_answers_db, get_questions_db

from boxing import boxing
from halo import Halo


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

        q = Question(key=key, message=message)
        questions.commit()

        # Start a spinner and then keep querying the answers table
        # until our key turns up.  We should probably timeout after
        # some reasonable time period.
        spinner = Halo(text="Waiting", spinner="dots")
        spinner.start()

        ## wait for key to turn up in answers table
        finish_before = datetime.now() + timedelta(seconds=cfg.timeout)

        result = None
        while result is None:
            result = Answer.get(key=key)
            if result or datetime.now() > finish_before:
                break

            time.sleep(0.25)

        spinner.stop()

        if result:
            res = boxing(result.message, style="double", padding=2, margin=1)
            print(res)
        else:
            print("❌ Query took too long...")
