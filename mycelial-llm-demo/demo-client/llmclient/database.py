import sqlite3

from pony import orm


def get_questions_db(path: str):
    questions = orm.Database()

    class Question(questions.Entity):
        _table_ = "questions"
        id = orm.PrimaryKey(int, auto=True)
        key = orm.Required(str)
        message = orm.Required(str)

    questions.bind(provider="sqlite", filename=path, create_db=True)
    questions.generate_mapping(create_tables=True)

    return questions, Question


def get_answers_db(path: str):
    answers = orm.Database()

    class Answer(answers.Entity):
        _table_ = "bacalhau"
        id = orm.PrimaryKey(int, auto=True)
        key = orm.Required(str)
        message = orm.Required(str)

    answers.bind(provider="sqlite", filename=path, create_db=True)
    answers.generate_mapping(create_tables=True)

    return answers, Answer


def get_data_db(path: str):
    return sqlite3.connect(path)
