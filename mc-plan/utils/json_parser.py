import json
import re

def safe_json_parse(text: str):
    """
    Safely parse text into JSON (dict or list).
    Handles cases where the response includes markdown fences (```json ... ```),
    or has trailing commas, or extra commentary before/after JSON.

    Returns:
        dict | list | None
    """

    if not text:
        return None

    # --- Step 1. Cleanup markdown code fences ---
    # 예: ```json { ... } ``` → { ... }
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text)
        text = re.sub(r"```$", "", text)
        text = text.strip()

    # --- Step 2. Find JSON object or array substring ---
    # 종종 모델이 JSON 앞뒤에 자연어 설명을 붙이므로 JSON만 추출
    json_pattern = r"(\{.*\}|\[.*\])"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        text = match.group(1)

    # --- Step 3. Remove trailing commas safely ---
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    # --- Step 4. Try parsing ---
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # fallback: replace single quotes or escape issues
        try:
            fixed = text.replace("'", '"')
            parsed = json.loads(fixed)
        except Exception:
            return None

    return parsed


if __name__ == '__main__':
    print(safe_json_parse("{ 'key': 'value', }"))