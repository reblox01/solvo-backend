import ast
import base64
import json
import logging
from io import BytesIO
from PIL import Image
import requests as http_requests

from constants import OPENCODE_ZEN_API_KEY

logger = logging.getLogger("solvo-backend")

# OpenCode Zen config
ZEN_BASE_URL = "https://opencode.ai/zen/v1"
ZEN_MODEL = "mimo-v2.5-free"
ZEN_TIMEOUT = 30


def _build_prompt(dict_of_vars: dict) -> str:
    dict_of_vars_str = json.dumps(dict_of_vars, ensure_ascii=False)
    return (
        f"You are a mathematical expression analyzer. Analyze the image and return ONLY a Python list of dictionaries.\n\n"
        f"RESPONSE FORMAT:\n"
        f"- Return ONLY a Python list of dictionaries\n"
        f"- Use proper Python string quotes\n"
        f"- Make sure all values are strings\n"
        f"- No explanations or additional text\n"
        f"- Format text with proper spaces between words\n\n"
        f"DETAILED RULES AND EXAMPLES:\n"
        f"1. Simple mathematical expressions:\n"
        f"   Input: 2 + 3 * 4\n"
        f"   Steps: (3 * 4) => 12, 2 + 12 = 14\n"
        f"   Return: [{{'expr': '2 + 3 * 4', 'result': '14'}}]\n\n"
        f"2. Complex expressions with PEMDAS:\n"
        f"   Input: 2 + 3 + 5 * 4 - 8 / 2\n"
        f"   Steps: 5 * 4 => 20, 8 / 2 => 4, 2 + 3 => 5, 5 + 20 => 25, 25 - 4 => 21\n"
        f"   Return: [{{'expr': '2 + 3 + 5 * 4 - 8 / 2', 'result': '21'}}]\n\n"
        f"3. Variable assignments:\n"
        f"   Input: x = 5\n"
        f"   Return: [{{'expr': 'x', 'result': '5', 'assign': True}}]\n\n"
        f"4. Equations with variables:\n"
        f"   Input: x^2 + 2x + 1 = 0\n"
        f"   Return: [{{'expr': 'x', 'result': '-1', 'assign': True}}]\n\n"
        f"5. Multiple variables:\n"
        f"   Input: 3y + 4x = 12, y = 2\n"
        f"   Return: [{{'expr': 'y', 'result': '2', 'assign': True}}, {{'expr': 'x', 'result': '1.5', 'assign': True}}]\n\n"
        f"6. Word problems and graphical math:\n"
        f"   Input: howmuchdoesittaketodropdown\n"
        f"   BAD: [{{'expr': 'howmuchdoesittaketodropdown', 'result': '10'}}]\n"
        f"   GOOD: [{{'expr': 'How much does it take to drop down', 'result': '10'}}]\n\n"
        f"   For problems involving scenarios, drawings, or diagrams:\n"
        f"   - Add proper spaces between words in the description\n"
        f"   - Make the text readable and natural\n"
        f"   - Keep mathematical precision in the result\n"
        f"   Example: [{{'expr': 'Car traveling 60 mph for 2 hours', 'result': '120'}}]\n\n"
        f"7. Abstract concepts:\n"
        f"   For drawings showing concepts:\n"
        f"   - Use proper spacing and punctuation\n"
        f"   - Make descriptions clear and readable\n"
        f"   Example: [{{'expr': 'Drawing shows heart shapes and positive emotions', 'result': 'love'}}]\n\n"
        f"Available variables and their values: {dict_of_vars_str}\n\n"
        f"IMPORTANT:\n"
        f"- Follow PEMDAS: Parentheses, Exponents, Multiplication/Division (left to right), Addition/Subtraction (left to right)\n"
        f"- Return ONLY the Python list, no other text\n"
        f"- All values must be strings\n"
        f"- Use proper Python dictionary format\n"
        f"- Always add spaces between words in text descriptions\n"
        f"- Make text human-readable and properly formatted\n"
    )


def _image_to_base64(img: Image) -> str:
    # Convert to RGB to handle palette, RGBA, LA, and other edge-case modes
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_opencode_zen(prompt: str, img: Image) -> str:
    """Call OpenCode Zen mimo-v2.5-free via OpenAI-compatible endpoint."""
    if not OPENCODE_ZEN_API_KEY:
        raise RuntimeError("OPENCODE_ZEN_API_KEY not configured")

    img_b64 = _image_to_base64(img)
    url = f"{ZEN_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENCODE_ZEN_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": ZEN_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    resp = http_requests.post(url, headers=headers, json=payload, timeout=ZEN_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_response(text: str) -> list[dict]:
    """Parse a Python-list-of-dicts response from any provider."""
    clean_text = text.strip()
    if not clean_text.startswith("["):
        start = clean_text.find("[")
        if start != -1:
            clean_text = clean_text[start:]
    if not clean_text.endswith("]"):
        end = clean_text.rfind("]")
        if end != -1:
            clean_text = clean_text[: end + 1]

    answers = []
    try:
        answers = ast.literal_eval(clean_text)
        if not isinstance(answers, list):
            answers = [answers] if isinstance(answers, dict) else []
    except Exception as e:
        logger.error("Failed to parse response: %s", e)
        return []

    formatted = []
    for answer in answers:
        if isinstance(answer, dict) and "expr" in answer and "result" in answer:
            answer.setdefault("assign", False)
            if isinstance(answer["expr"], str):
                answer["expr"] = " ".join(answer["expr"].replace("_", " ").split())
            formatted.append(answer)
    return formatted


def analyze_image(img: Image, dict_of_vars: dict) -> list[dict]:
    """Analyze an image using OpenCode Zen mimo-v2.5-free."""
    prompt = _build_prompt(dict_of_vars)
    text = _call_opencode_zen(prompt, img)
    return _parse_response(text)
