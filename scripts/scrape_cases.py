import os
import time
import json
import uuid
import random
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
from google import genai as gai
from pydantic import BaseModel, Field
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import uuid

# Load API Key
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

gclient = gai.Client(api_key=os.environ["GEMINI_API_KEY"])
qdrant = QdrantClient(url=os.environ.get("QDRANT_URL"), api_key=os.environ.get("QDRANT_API_KEY"))

class CaseExtraction(BaseModel):
    id: str = Field(description="Unique identifier or citation")
    title: str = Field(description="Case title (Player 1 vs Player 2)")
    forum: str = Field(description="Legal forum")
    year: int = Field(description="Year of the judgment")
    dispute_type: str = Field(description="Categorize into exactly one of: 'MSME Supply Dispute', 'Consumer Product Defect', 'Contract Breach', 'Service Failure', 'Payment Default', or 'Property Dispute'")
    facts: str = Field(description="Summary of facts")
    disputed_clause: str = Field(description="The clause or legal principle in dispute")
    claimed_amount: int = Field(description="Amount claimed by petitioner")
    settled_amount: int = Field(description="Amount awarded or settled")
    win_probability: int = Field(description="Estimated win probability based on this precedent (0-100)")
    duration_months: int = Field(description="Estimated case duration in months")
    outcome: str = Field(description="Summary of the judgment or settlement")
    key_principle: str = Field(description="The key legal principle established")

QUERIES = [
    "MSME supply dispute defective goods",
    "consumer product defect NCDRC compensation",
    "breach of contract commercial real estate",
    "service failure deficiency compensation",
    "payment default commercial invoice"
]

def search_kanoon(query, pages=1):
    links = []
    print(f"[*] Searching Indian Kanoon for: {query}")
    for page in range(pages):
        target_url = f"https://indiankanoon.org/search/?formInput={urllib.parse.quote(query)}&pagenum={page}"
        
        # Route through Residential Proxy if running on Google Cloud
        if os.environ.get("SCRAPER_API_KEY"):
            api_key = os.environ.get("SCRAPER_API_KEY")
            proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={urllib.parse.quote(target_url)}"
            req = urllib.request.Request(proxy_url)
        else:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            
        try:
            html = urllib.request.urlopen(req).read()
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.select('.result_title a'):
                href = a['href']
                if '/doc/' in href or '/docfragment/' in href:
                    doc_id = href.split('/')[-2]
                    links.append(f'https://indiankanoon.org/doc/{doc_id}/')
        except Exception as e:
            print(f"Error fetching page {page} for query {query}: {e}")
            if "403" in str(e) or "Forbidden" in str(e):
                print("[!] IP Rate Limit hit! Stopping pagination for this query.")
                break
        
        # Organic human-like delay between 10 to 20 seconds to bypass Kanoon's Anti-Bot system
        delay = random.randint(10, 20)
        print(f"  [Sleep] Waiting {delay}s before next page...")
        time.sleep(delay)
    return list(set(links))

def extract_case_text(url):
    if os.environ.get("SCRAPER_API_KEY"):
        api_key = os.environ.get("SCRAPER_API_KEY")
        proxy_url = f"http://api.scraperapi.com?api_key={api_key}&url={urllib.parse.quote(url)}"
        req = urllib.request.Request(proxy_url)
    else:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
    try:
        html = urllib.request.urlopen(req).read()
        soup = BeautifulSoup(html, 'html.parser')
        text = ""
        for p in soup.find_all('p'):
            text += p.get_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from {url}: {e}")
        return ""

def process_case(url):
    text = extract_case_text(url)
    if not text or len(text) < 500:
        return None
    
    print(f"[*] Parsing {url} with Gemini...")
    try:
        prompt = f"Extract the key case details from the following Indian legal judgment text. Be accurate. Only output a valid JSON matching the schema.\n\nText: {text[:15000]}"
        res = gclient.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": CaseExtraction
            }
        )
        data = json.loads(res.text)
        data["source_url"] = url
        
        embed_str = data["facts"] + " " + data["disputed_clause"]
        print(f"[*] Embedding case...")
        resp = gclient.models.embed_content(model="gemini-embedding-001", contents=embed_str)
        embedding = list(resp.embeddings[0].values)
        
        # Create a deterministic UUID based on the URL so running twice overwrites instead of duplicates
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
        qdrant.upsert(
            collection_name="nyaybot_cases",
            points=[PointStruct(id=point_id, vector=embedding, payload=data)]
        )
        return data
    except Exception as e:
        print(f"Error parsing case {url}: {e}")
        return None

def main():
    if not qdrant.collection_exists("nyaybot_cases"):
        qdrant.create_collection(
            collection_name="nyaybot_cases",
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE)
        )
        
    extracted_count = 0
    MAX_CASES = 100000

    all_links = []
    for q in QUERIES:
        all_links.extend(search_kanoon(q, pages=2000))
    
    all_links = list(set(all_links))
    print(f"[*] Found {len(all_links)} total links. Processing up to {MAX_CASES}...")
    
    for i, link in enumerate(all_links):
        if extracted_count >= MAX_CASES:
            break
        print(f"\n({i+1}/{len(all_links)}) Processing: {link}")
        case_data = process_case(link)
        if case_data:
            extracted_count += 1
            print(f"[+] Successfully structured and uploaded to Qdrant: {case_data['title']}")
        
        delay = random.randint(10, 20)
        print(f"  [Sleep] Waiting {delay}s before next case extraction...")
        time.sleep(delay) 

    print(f"\n[*] Done! Uploaded {extracted_count} new cases directly to Qdrant Cloud.")

if __name__ == "__main__":
    main()
