from sentence_transformers import SentenceTransformer, util

model = None


def get_model():
    global model

    if model is None:
        model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
    return model


def get_query(sentence, data, limit):
    all_sentences = [sentence for obj in data for sentence in obj["sentence"]]
    all_sentences.append(sentence)

    # Encode all sentences to get their embeddings
    embeddings = get_model().encode(all_sentences, convert_to_tensor=True)

    # Compute cosine similarity between the embeddings of the input sentence and all other sentences
    similarity_scores = util.pytorch_cos_sim(embeddings[-1], embeddings[:-1])[0]

    # Convert similarity scores to numpy array for easier handling
    similarity_scores = similarity_scores.cpu().numpy()

    # Find the index of the most similar sentence
    most_similar_index = similarity_scores.argmax()

    # Find the object in the JSON array that contains the most similar sentence
    most_similar_object = None
    for obj in data:
        if all_sentences[most_similar_index] in obj["sentence"]:
            most_similar_object = obj
            break
        return None

    print(f"Matched sentence: {all_sentences[most_similar_index]}")
    print(
        f"Similarity score was {similarity_scores[most_similar_index]:.2f} and limit was {limit}"
    )

    if similarity_scores[most_similar_index] > limit:
        return most_similar_object["query"]

    return None
