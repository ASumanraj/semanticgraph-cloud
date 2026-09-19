from gliner import GLiNER

def extract_entities(text: str, labels: list[str]) -> list[dict]:
    model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
    return model.predict_entities(text, labels)
