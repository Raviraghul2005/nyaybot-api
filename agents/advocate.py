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
Key rule: Treat "Party 1 Current Position" as your anchor for Round 1. Do NOT jump straight to the full claimed amount unless your anchor is already close to it.
- Round 1: Opening offer must be very close to ₹{current_position:,} (within +/-10%). Argue why this anchor is fair, citing precedents.
- Round 2: Concede 10-20% FROM your previous position (the new Party 1 Current Position you received). Justify why you cannot go lower.
- Round 3: Make a final offer close to the ZOPA midpoint, but keep it consistent with your previous movement (do not make extreme jumps).

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
- Round 1: Opening offer must be very close to ₹{current_position:,} (within +/-10%). Do NOT start at ₹0 unless your anchor is already near ₹0.
- Round 2: Concede moderately FROM your previous position (the new Party 2 Current Position you received). Move upward (you become more accommodating), but avoid extreme concessions.
- Round 3: Make a final counter-offer close to the ZOPA midpoint, consistent with your prior movement.

Write 2-3 sentences as Advocate B speaking directly. Cite specific legal defences and precedents.
Return ONLY a JSON object:
{{"position": <integer rupee amount>, "message": "your message here"}}"""

    raw = _call(prompt)
    return safe_parse_json(raw)
