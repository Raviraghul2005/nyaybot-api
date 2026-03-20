import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from agents.utils import safe_parse_json

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-2.5-flash"

def run_drafter(intake: dict, settlement_amount: int, party1: str, party2: str,
                case_id: str, precedents: list) -> dict:
    """
    Generates a formal settlement agreement text grounded in Indian contract law.
    Returns: {agreement_text, key_terms}
    """
    today = __import__("datetime").date.today().strftime("%d %B %Y")
    prec_refs = ", ".join([p["id"] for p in precedents[:2]])

    prompt = f"""You are the Drafter Agent for NyayBot. Draft a formal settlement agreement under Indian law.

Case Details:
- Case ID: {case_id}
- Party 1 (Claimant): {party1}
- Party 2 (Respondent): {party2}
- Dispute Type: {intake.get('dispute_type')}
- Original Claim: ₹{intake.get('amount', 0):,}
- Settlement Amount: ₹{settlement_amount:,}
- Precedents Referenced: {prec_refs}
- Date: {today}

Draft a complete, formal settlement agreement including:
1. Parties section
2. Recitals (background)
3. Settlement terms (payment, timeline, conditions)
4. Release of claims clause
5. Confidentiality clause
6. Governing law (Indian law, jurisdiction of {intake.get('forum_recommendation', 'MSME Samadhaan')})
7. Signatures block

Also extract key_terms as a list of {{"term": ..., "value": ...}} objects.

Return ONLY this JSON:
{{
  "agreement_text": "Full formal agreement text here...",
  "key_terms": [
    {{"term": "Settlement Amount", "value": "₹{settlement_amount:,}"}},
    {{"term": "Payment Timeline", "value": "15 working days"}},
    {{"term": "Forum", "value": "{intake.get('forum_recommendation', 'MSME Samadhaan')}"}},
    {{"term": "Date", "value": "{today}"}}
  ]
}}"""

    model = genai.GenerativeModel(MODEL)
    resp = model.generate_content(prompt)
    return safe_parse_json(resp.text)
