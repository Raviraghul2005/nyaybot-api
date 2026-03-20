import os
import json
import re
import numpy as np
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

CASES_PATH = Path(__file__).parent.parent / "data" / "cases.json"

# Load cases once at startup (now includes pre-computed embeddings)
with open(CASES_PATH, encoding="utf-8") as f:
    CASES = json.load(f)

EMBED_MODEL = "models/text-embedding-004"

def _embed(text: str) -> list[float]:
    result = genai.embed_content(model=EMBED_MODEL, content=text)
    return result["embedding"]

def _cosine(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0

def _keyword_score(query: str, text: str) -> float:
    """Bounded Jaccard similarity for keyword overlap [0, 1]"""
    q_words = set(re.findall(r"\w+", query.lower()))
    t_words = set(re.findall(r"\w+", text.lower()))
    if not q_words or not t_words:
        return 0.0
    return len(q_words & t_words) / len(q_words | t_words)

def search_precedents(query: str, top_k: int = 3, dispute_type: str = None) -> list[dict]:
    """
    Return top_k cases most similar to the query.
    1. Filters by dispute_type first (strict).
    2. Falls back to all cases if zero matches found.
    3. Calculates hybrid score (70% semantic, 30% keyword).
    Uses pre-computed embeddings stacked in cases.json.
    """
    try:
        q_emb = _embed(query)
    except Exception as e:
        print(f"[RAG] Query Embedding failed ({e})")
        q_emb = None

    scored = []
    
    # 1. Filter by dispute type
    filtered_cases = CASES
    type_matched = False
    
    if dispute_type:
        exact_matches = [c for c in CASES if c.get("dispute_type", "").lower() == dispute_type.lower()]
        if len(exact_matches) > 0:
            filtered_cases = exact_matches
            type_matched = True

    for case in filtered_cases:
        c_text = case.get("facts", "") + " " + case.get("disputed_clause", "")
        
        # Semantic Score (requires q_emb and case embedding)
        sem_score = 0.0
        if q_emb and "embedding" in case:
            sem_score = _cosine(q_emb, case["embedding"])
            
        # Keyword Score
        kw_score = _keyword_score(query, c_text)
        
        # Hybrid Score: 70% semantic, 30% keyword
        if sem_score > 0:
            final_score = (sem_score * 0.7) + (kw_score * 0.3)
        else:
            final_score = kw_score

        # Penalty if we fell back to all cases and this one doesn't match type
        if dispute_type and not type_matched:
            if case.get("dispute_type", "").lower() != dispute_type.lower():
                final_score *= 0.8  # 20% penalty
                
        # Remove embedding vector to save bandwidth
        ret_case = {k: v for k, v in case.items() if k != "embedding"}
        ret_case["similarity"] = round(final_score * 100, 1)
        scored.append(ret_case)

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]
