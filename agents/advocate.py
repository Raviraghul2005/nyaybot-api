import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from agents.utils import safe_parse_json

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-2.5-flash"
REQUEST_TIMEOUT_SECONDS = 30

def _call(prompt: str) -> str:
    model = genai.GenerativeModel(MODEL)
    resp = model.generate_content(
        prompt,
        request_options={"timeout": REQUEST_TIMEOUT_SECONDS},
    )
    return resp.text.strip()

def run_advocate_a(intake: dict, precedents: list, current_position: int, round_num: int, custom_strategy: str = None) -> dict:
    """Party 1 advocate — argues for the claimant."""
    prec_text = "\n".join([
        f"- {p['title']} ({p['forum']}, {p['year']}): settled at ₹{p['settled_amount']:,}. {p['key_principle']}"
        for p in precedents
    ])
    prompt = f"""You are Advocate A in a NyayBot AI negotiation session. You represent PARTY 1 (Claimant).

Case Facts: {json.dumps(intake, ensure_ascii=False)}
Relevant Indian Precedents:
{prec_text}

Current Round: {round_num}
Party 1 Current Position: ₹{current_position:,}

{f"CRITICAL INSTRUCTION FROM YOUR HUMAN CLIENT: Use exactly this strategy/argument: '{custom_strategy}'. You MUST dramatically incorporate this demand into your message!" if custom_strategy else ""}

Your job: State Party 1's negotiation position firmly but reasonably, grounded in the precedents above.
- Round 1: State opening position strongly (claim full amount, cite precedents)
- Round 2: Show some movement (concede 10-20%), but justify why you cannot go lower
- Round 3: Make a final offer close to ZOPA midpoint

Write 2-3 sentences as Advocate A speaking directly. Be specific: cite case names, amounts, legal principles.
Return ONLY a JSON object:
{{"position": <integer rupee amount>, "message": "your message here"}}"""

    raw = _call(prompt)
    return safe_parse_json(raw)


def run_advocate_b(intake: dict, precedents: list, current_position: int, round_num: int) -> dict:
    """Party 2 advocate — argues for the respondent/supplier."""
    prec_text = "\n".join([
        f"- {p['title']} ({p['forum']}, {p['year']}): {p['key_principle']}"
        for p in precedents
    ])
    prompt = f"""You are Advocate B in a NyayBot AI negotiation session. You represent PARTY 2 (Respondent/Supplier).

Case Facts: {json.dumps(intake, ensure_ascii=False)}
Relevant Indian Precedents:
{prec_text}

Current Round: {round_num}
Party 2 Current Position: ₹{current_position:,}

Your job: Counter Party 1's claims while defending your client, grounded in precedents.
- Round 1: Deny or heavily discount liability (start at ₹0 or very low)
- Round 2: Acknowledge partial responsibility, offer 25-35% of claimed amount
- Round 3: Move to 50-55% of claimed amount as final counter-offer

Write 2-3 sentences as Advocate B speaking directly. Cite specific legal defences and precedents.
Return ONLY a JSON object:
{{"position": <integer rupee amount>, "message": "your message here"}}"""

    raw = _call(prompt)
    return safe_parse_json(raw)
