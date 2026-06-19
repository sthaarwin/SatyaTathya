import os
import chromadb
from chromadb.config import Settings
import numpy as np


CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_data")
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(name="satya_claims")

model = None


def get_embedding_model():
    """
    Get the sentence-transformer model instance, initializing it only once on first call.
    This prevents unnecessary network lookups or heavy model loading during module import.
    """
    global model
    if model is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

def encode_text(text: str):
    """
    Generate vector embedding from text using the lazy-loaded model.
    """
    return get_embedding_model().encode(text).tolist()

def add_claim_to_db(claim_id: str, core_news_claim: str, metadata: dict):
    """Add a verified claim to ChromaDB."""
    embedding = encode_text(core_news_claim)
    collection.add(
        ids=[claim_id],
        embeddings=[embedding],
        documents=[core_news_claim],
        metadatas=[metadata]
    )

def search_similar_claims(core_news_claim: str, threshold: float = 1.0):
    embedding = encode_text(core_news_claim)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=3
    )
    
    matches = []
    if results['distances'] and results['distances'][0]:
        for i, distance in enumerate(results['distances'][0]):
            if distance < threshold:
                matches.append({
                    "id": results['ids'][0][i],
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": distance
                })
    return matches

def compute_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity between two texts using embeddings."""
    model = get_embedding_model()
    emb1 = model.encode(text1)
    emb2 = model.encode(text2)
    similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    return float(similarity)

def clear_chroma():
    """Clear all vectors from ChromaDB."""
    try:
        all_ids = collection.get().get('ids', [])
        if all_ids:
            collection.delete(ids=all_ids)
        return len(all_ids)
    except:
        return 0
