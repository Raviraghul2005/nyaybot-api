import os
import json
import time
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import google.generativeai as genai
from pydantic import BaseModel, Field
from pathlib import Path
from dotenv import load_dotenv

# Load API Key
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")

class CaseExtraction(BaseModel):
    id: str = Field(description="Unique identifier or citation (e.g. from the title)")
    title: str = Field(description="Case title (Player 1 vs Player 2)")
    forum: str = Field(description="Legal forum (e.g., NCDRC, Supreme Court, High Court)")
    year: int = Field(description="Year of the judgment")
    dispute_type: str = Field(description="Categorize into exactly one of: 'MSME Supply Dispute', 'Consumer Product Defect', 'Contract Breach', 'Service Failure', 'Payment Default', or 'Property Dispute'")
    facts: str = Field(description="Summary of facts (3-4 sentences)")
    disputed_clause: str = Field(description="The clause or legal principle in dispute")
    claimed_amount: int = Field(description="Amount claimed by petitioner (if unknown, estimate realistically based on facts between 50000 and 5000000)")
    settled_amount: int = Field(description="Amount awarded or settled (if unknown, estimate realistically based on outcome)")
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
        url = f"https://indiankanoon.org/search/?formInput={urllib.parse.quote(query)}&pagenum={page}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
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
        time.sleep(1) # Be nice to their servers
    return list(set(links))

def extract_case_text(url):
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

def embed_text(text):
    result = genai.embed_content(model="models/text-embedding-004", content=text)
    return result["embedding"]

def process_case(url):
    text = extract_case_text(url)
    if not text or len(text) < 500:
        return None
    
    print(f"[*] Parsing {url} with Gemini...")
    try:
        prompt = f"Extract the key case details from the following Indian legal judgment text. Be accurate. Only output a valid JSON matching the schema.\n\nText: {text[:15000]}"
        res = model.generate_content(
            prompt, 
            generation_config={
                "response_mime_type": "application/json", 
                "response_schema": CaseExtraction
            }
        )
        data = json.loads(res.text)
        data["source_url"] = url
        
        # Build embedding string: facts + disputed_clause
        embed_str = data["facts"] + " " + data["disputed_clause"]
        print(f"[*] Embedding case...")
        data["embedding"] = embed_text(embed_str)
        return data
    except Exception as e:
        print(f"Error parsing case {url}: {e}")
        return None

def main():
    cases = []
    MAX_CASES = 50
    # Attempt to gather enough links
    all_links = []
    for q in QUERIES:
        all_links.extend(search_kanoon(q, pages=1))
    
    # Shuffle or process
    all_links = list(set(all_links))
    print(f"[*] Found {len(all_links)} total links. Processing up to {MAX_CASES}...")
    
    for i, link in enumerate(all_links):
        if len(cases) >= MAX_CASES:
            break
        print(f"\n({i+1}/{len(all_links)}) Processing: {link}")
        case_data = process_case(link)
        if case_data:
            cases.append(case_data)
            print(f"[+] Successfully structured case: {case_data['title']}")
        time.sleep(1) # Rate limit Gemini API

    # Save to cases.json
    out_path = Path(__file__).parent.parent / "data" / "cases.json"
    print(f"\n[*] Saving {len(cases)} cases with pre-computed embeddings to {out_path}...")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)
    print("[*] Done!")

if __name__ == "__main__":
    main()
