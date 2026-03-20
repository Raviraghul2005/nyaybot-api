import json
import re

def safe_parse_json(raw_text: str) -> dict:
    """Safely extracts and parses JSON from Gemini output, handling markdown wrappers."""
    if not isinstance(raw_text, str):
        return {}

    raw_text = raw_text.strip()
    
    # Try direct parse
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    
    # Strip markdown code blocks
    text = raw_text
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # Regex fallback to find JSON objects
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
            
    print(f"[ERROR] safe_parse_json failed on: {raw_text[:200]}...")
    return {}
