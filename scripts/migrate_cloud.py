import os
import json
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

qdrant_url = os.environ.get("QDRANT_URL")
qdrant_api_key = os.environ.get("QDRANT_API_KEY")
client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

print("[*] Connecting to Qdrant Cloud Cluster...")
if not client.collection_exists("nyaybot_cases"):
    client.create_collection(
        collection_name="nyaybot_cases",
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )
    print("[+] Created collection 'nyaybot_cases' with 768 dimensions.")

cases_path = Path(__file__).parent.parent / "data" / "cases.json"
with open(cases_path, "r", encoding="utf-8") as f:
    cases = json.load(f)

points = []
for i, c in enumerate(cases):
    vector = c.get("embedding")
    payload = {k: v for k, v in c.items() if k != "embedding"}
    if vector:
        points.append(PointStruct(id=i+1, vector=vector, payload=payload))

if points:
    client.upsert(collection_name="nyaybot_cases", points=points)
    print(f"[+] Successfully migrated {len(points)} existing cases from JSON to Qdrant Cloud!")
else:
    print("[-] No embeddings found in cases.json to migrate.")
