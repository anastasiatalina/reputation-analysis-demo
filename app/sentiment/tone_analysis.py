from transformers import pipeline
from app.config import load_config

_sentiment_analyzer = None


def _get_sentiment_analyzer():
    """
    Lazily create the Transformers pipeline to avoid heavy initialization at import time.
    """
    global _sentiment_analyzer
    if _sentiment_analyzer is not None:
        return _sentiment_analyzer
    cfg = load_config()
    _sentiment_analyzer = pipeline(
        "sentiment-analysis",
        model=cfg.sentiment_model,
        revision="714eb0f",
    )
    return _sentiment_analyzer

def _score(text: str) -> float:
    """
    Run the shared sentiment pipeline on `text` and return a signed score in [-1, 1].

    truncation=True is applied here, once, so every caller is protected against the
    model's max token length (DistilBERT: 512 tokens) raising instead of truncating.
    """
    sentiment_analyzer = _get_sentiment_analyzer()
    result = sentiment_analyzer(text, truncation=True)
    return result[0]["score"] if result[0]["label"] == "POSITIVE" else -result[0]["score"]

def analyze_tone(text):
    return _score(text)

def analyze_long_tone(text):
    # Max input length for the model (token budget).
    MAX_LENGTH = 450

    # Split long text into chunks.
    if len(text.split()) > 200:
        sentences = text.split('.')
        chunks = []
        current_chunk = []
        current_length = 0

        # Group sentences into chunks.
        for sentence in sentences:
            words = sentence.split()
            sentence_length = len(words)

            # Split very long sentences.
            if sentence_length > 200:
                # Split by comma, then by words if still too long.
                sub_sentences = sentence.split(',')
                for sub in sub_sentences:
                    if len(sub.split()) > 200:
                        # If still too long, chunk by words.
                        words = sub.split()
                        for i in range(0, len(words), 200):
                            chunk = ' '.join(words[i:i+200])
                            if chunk.strip():
                                chunks.append(chunk)
                    else:
                        if sub.strip():
                            chunks.append(sub)
            # Append sentence if within limits.
            elif current_length + sentence_length <= 200:
                current_chunk.append(sentence)
                current_length += sentence_length
            else:
                # Save the current chunk and start a new one.
                if current_chunk:
                    chunks.append('. '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length

        # Add the last chunk.
        if current_chunk:
            chunks.append('. '.join(current_chunk))

        # Score each chunk.
        scores = []
        for chunk in chunks:
            if chunk.strip():
                try:
                    scores.append(_score(chunk[:MAX_LENGTH]))
                except Exception as e:
                    print(f"Chunk analysis error: {e}")
                    continue

        # Return the average score.
        return sum(scores) / len(scores) if scores else 0

    # Short text path.
    try:
        return _score(text[:MAX_LENGTH])
    except Exception as e:
        print(f"Short-text analysis error: {e}")
        return 0
