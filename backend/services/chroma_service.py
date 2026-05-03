import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Initialize ChromaDB client to store data locally
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_data")
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_or_create_collection(name="satya_claims")

# Initialize embedding model (using a lightweight model suitable for semantic matching)
model = SentenceTransformer('all-MiniLM-L6-v2')

def encode_text(text: str):
    """Generate vector embedding from text."""
    return model.encode(text).tolist()

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
    """
    Search ChromaDB for semantically similar claims.
    Using L2 distance. Lower distance means higher similarity.
    """
    embedding = encode_text(core_news_claim)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=3
    )
    
    matches = []
    if results['distances'] and results['distances'][0]:
        for i, distance in enumerate(results['distances'][0]):
            if distance < threshold: # If distance is small enough, it's a match
                matches.append({
                    "id": results['ids'][0][i],
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": distance
                })
    return matches
