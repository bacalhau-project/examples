from datetime import datetime, timedelta
import hashlib
import json
import readline  # importing applies effect
import time

from .config import Config
from .database import get_answers_db, get_data_db, get_questions_db

from boxing import boxing
from halo import Halo
from tabulate import tabulate


def rephrase(spinner=None):
    if spinner:
        spinner.succeed("Query complete")
    print("Please rephrase query\n")


def display_answer(data_db, answer=None, spinner=None):
    if not answer:
        if spinner:
            spinner.fail("Query took too long")
        print("")
        return

    if answer:
        result = json.loads(answer.message)
        if result.get("query", "") == "":
            rephrase(spinner)
            return

        if spinner:
            spinner.succeed("Query successful")
        print("")

        # Verify we got a safe query
        qm_count = result["query"].count("?")
        if qm_count > 0 and qm_count != len(result["replacements"]):
            rephrase(spinner)
            return

        if qm_count == 0:
            result["replacements"] = []

        c = data_db.cursor()
        c.execute(result["query"], result["replacements"])
        rows = c.fetchall()
        columns = [v[0] for v in c.description]

        t = tabulate(
            rows,
            headers=columns,
            floatfmt=".2f",
            tablefmt="psql",
        )
        print(t)


def run(cfg: Config):
    questions, Question = get_questions_db(cfg.questions)
    answers, Answer = get_answers_db(cfg.answers)
    engines = get_data_db(cfg.data)

    while True:
        message = input("> ")
        if message.lower() == ".q":
            break
        elif message.strip() == "":
            continue

        # Strip ?
        message = message.replace("?", "")

        key = hashlib.md5(message.encode("utf-8")).hexdigest()

        # Check for existing answer
        result = Answer.get(key=key)
        if result is not None:
            display_answer(engines, result, None)
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

        display_answer(engines, result, spinner)
