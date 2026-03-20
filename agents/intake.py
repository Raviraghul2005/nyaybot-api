import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from agents.utils import safe_parse_json

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-2.5-flash"

def run_intake(raw_text: str) -> dict:
    """
    Extracts structured dispute facts from free-form text.
    Returns: {dispute_type, amount, key_facts, disputed_clauses, forum_recommendation}
    """
    prompt = f"""You are the Intake Agent for NyayBot, an Indian legal dispute intelligence system.

Analyze this dispute description and extract structured information.

Dispute Description:
{raw_text}

Return a JSON object with EXACTLY these fields:
{{
  "dispute_type": "one of: MSME Supply Dispute | Consumer Product Defect | Service Failure | Contract Breach | Payment Default | Property Dispute",
  "amount": <integer rupee amount, 0 if unclear>,
  "key_facts": ["fact 1", "fact 2", "fact 3", ...],
  "disputed_clauses": ["clause or legal issue 1", "clause or legal issue 2", ...],
  "forum_recommendation": "one of: MSME Samadhaan Facilitation Council | NCDRC | District Consumer Forum | Civil Court",
  "case_summary": "2-3 sentence summary of the dispute",
  "strength_assessment": "Strong | Moderate | Weak",
  "strength_reasoning": "1-2 sentences explaining why"
}}

Return ONLY valid JSON, no markdown, no explanation."""

    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(prompt)
    return safe_parse_json(response.text)
