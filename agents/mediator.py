import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from agents.utils import safe_parse_json

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-2.5-flash"

def run_mediator(intake: dict, precedents: list, a_position: int, b_position: int,
                 a_message: str, b_message: str, round_num: int) -> dict:
    """
    Fisher & Ury principled mediator. Computes ZOPA, suggests convergence.
    Returns: {zopa_low, zopa_high, message, converged, recommended_settlement}
    """
    avg_settled = sum(p["settled_amount"] for p in precedents) // len(precedents) if precedents else 150000
    prec_text = "\n".join([
        f"- {p['title']}: settled at ₹{p['settled_amount']:,}"
        for p in precedents
    ])

    prompt = f"""You are the AI Mediator in a NyayBot negotiation session, trained in Fisher & Ury principled negotiation.

Case: {intake.get('dispute_type')}, Amount Claimed: ₹{intake.get('amount', 0):,}

Round {round_num} Positions:
- Advocate A (Claimant): ₹{a_position:,} — "{a_message}"
- Advocate B (Respondent): ₹{b_position:,} — "{b_message}"

Relevant Precedent Settlements:
{prec_text}
Average precedent settlement: ₹{avg_settled:,}

Your job as Mediator:
1. Identify the Zone Of Possible Agreement (ZOPA) — the range between B's position and A's position
2. Detect if positions have converged (gap < 20% of original claim, or round 3)
3. Recommend a fair settlement at the midpoint, anchored to precedent average
4. Write a 2-3 sentence mediator statement using principled negotiation language

Return ONLY this JSON:
{{
  "zopa_low": <integer — Party B position>,
  "zopa_high": <integer — Party A position>,
  "recommended_settlement": <integer — fair midpoint near precedent average>,
  "converged": <true if gap < 20% of original claim OR round >= 3>,
  "message": "Your mediator statement here"
}}"""

    model = genai.GenerativeModel(MODEL)
    resp = model.generate_content(prompt)
    return safe_parse_json(resp.text)
