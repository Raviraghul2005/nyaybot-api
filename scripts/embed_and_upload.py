"""
One-time script: generates embeddings for all cases in cases.json
and uploads all vectors to Qdrant Cloud.

Run from nyaybot-api/:
  python scripts/embed_and_upload.py
"""
import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai as gai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

gclient = gai.Client(api_key=os.environ["GEMINI_API_KEY"])
qdrant  = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])

COLLECTION  = "nyaybot_cases"
EMBED_MODEL = "gemini-embedding-001"
VECTOR_DIM  = 3072

# Recreate collection with correct dimensions
if qdrant.collection_exists(COLLECTION):
    qdrant.delete_collection(COLLECTION)
    print(f"[*] Deleted old collection (wrong dimensions).")
qdrant.create_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
)
print(f"[+] Created collection '{COLLECTION}' with {VECTOR_DIM} dims.")


# Load cases
cases_path = Path(__file__).parent.parent / "data" / "cases.json"
with open(cases_path, "r", encoding="utf-8") as f:
    cases = json.load(f)
print(f"[*] Loaded {len(cases)} cases.")

points = []
for i, case in enumerate(cases):
    embed_text = (
        case.get("facts", "") + " "
        + case.get("disputed_clause", "") + " "
        + case.get("key_principle", "")
    ).strip()

    try:
        resp   = gclient.models.embed_content(model=EMBED_MODEL, contents=embed_text)
        vector = resp.embeddings[0].values
    except Exception as e:
        print(f"  [!] Embedding failed for case {i+1}: {e}. Skipping.")
        continue

    payload = {k: v for k, v in case.items() if k != "embedding"}
    points.append(PointStruct(id=i + 1, vector=vector, payload=payload))
    print(f"  [{i+1}/{len(cases)}] Embedded: {case.get('title', 'Unknown')[:60]}")
    time.sleep(0.3)

if points:
    qdrant.upsert(collection_name=COLLECTION, points=points, wait=True)
    info = qdrant.get_collection(COLLECTION)
    print(f"\n[+] Uploaded {len(points)} cases. Qdrant now holds {info.points_count} total points.")
else:
    print("[-] No points to upload.")
