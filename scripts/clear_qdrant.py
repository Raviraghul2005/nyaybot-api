import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

# Load secrets
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

qdrant = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
COLLECTION = "nyaybot_cases"

print(f"[*] Connecting to Qdrant Cloud...")

if qdrant.collection_exists(COLLECTION):
    print(f"[*] Deleting existing collection '{COLLECTION}'...")
    qdrant.delete_collection(COLLECTION)
    print(f"[+] Collection deleted successfully.")
else:
    print(f"[*] Collection '{COLLECTION}' does not exist.")

# Recreate the collection with the correct 3072 dimensions for google-genai
print(f"[*] Creating fresh collection '{COLLECTION}'...")
qdrant.create_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(size=3072, distance=Distance.COSINE)
)
print(f"[+] Clean slate ready! You can now run scrape_cases.py")
