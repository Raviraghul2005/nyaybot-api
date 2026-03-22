import os
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from google import genai as gai
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

gclient = gai.Client(api_key=os.environ["GEMINI_API_KEY"])
qdrant  = QdrantClient(
    url=os.environ.get("QDRANT_URL"),
    api_key=os.environ.get("QDRANT_API_KEY")
)

COLLECTION  = "nyaybot_cases"
EMBED_MODEL = "gemini-embedding-001"

def _embed(text: str) -> list[float]:
    resp = gclient.models.embed_content(model=EMBED_MODEL, contents=text)
    return list(resp.embeddings[0].values)

def search_precedents(query: str, top_k: int = 3, dispute_type: str = None) -> list[dict]:
    """
    Search Qdrant Cloud using Gemini gemini-embedding-001 (3072-dim).
    Filters by dispute_type when provided, falls back to global search on error.
    """
    query_filter = None
    if dispute_type:
        query_filter = Filter(
            must=[FieldCondition(key="dispute_type", match=MatchValue(value=dispute_type))]
        )

    try:
        q_emb = _embed(query)
    except Exception as e:
        print(f"[RAG] Embedding failed: {e}")
        return []

    try:
        result = qdrant.query_points(
            collection_name=COLLECTION,
            query=q_emb,
            query_filter=query_filter,
            limit=top_k
        )
        results = result.points
    except Exception as e:
        print(f"[RAG] Qdrant search failed ({e}), retrying without filter...")
        try:
            result = qdrant.query_points(
                collection_name=COLLECTION,
                query=q_emb,
                limit=top_k
            )
            results = result.points
        except Exception as e2:
            print(f"[RAG] Total failure: {e2}")
            return []

    scored = []
    for r in results:
        case = dict(r.payload)
        case["similarity"] = round(r.score * 100, 1)
        scored.append(case)

    return scored
