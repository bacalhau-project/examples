import spacy

nlp = None


def get_NLP():
    global nlp

    if nlp is None:
        nlp = spacy.load("en_core_web_sm")
    return nlp


def get_replacements(sentence):
    doc = get_NLP()(sentence)
    return [ent.text for ent in doc.ents if ent.label_ in ["CARDINAL", "ORDINAL"]]
