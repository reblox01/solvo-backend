from google import genai
import ast
import base64
import concurrent.futures
import json
import logging
import time
from io import BytesIO
from PIL import Image
import requests as http_requests

from constants import GEMINI_API_KEY, NIM_API_KEY

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
logger = logging.getLogger("solvo-backend")

# Gemini models in priority order
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

# NVIDIA NIM config (OpenAI-compatible endpoint)
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODELS = ["nvidia/nemotron-nano-12b-v2-vl", "meta/llama-3.2-11b-vision-instruct"]

# Retry config for the fallback retry after race
FALLBACK_RETRIES = 1
FALLBACK_RETRY_DELAY = 3

# Timeout for each provider call during the race (seconds)
RACE_TIMEOUT = 8


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


def _call_gemini(prompt: str, img: Image) -> str:
    """Try all Gemini models in order. Returns raw response text or raises."""
    last_error = None
    for model_name in GEMINI_MODELS:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=[prompt, img],
            )
            logger.info("Gemini model %s succeeded", model_name)
            return response.text
        except Exception as e:
            last_error = e
            logger.warning("Gemini model %s failed: %s", model_name, e)
    raise RuntimeError(f"Gemini failed: {last_error}")


def _call_nim(prompt: str, img: Image) -> str:
    """Call NVIDIA NIM via OpenAI-compatible endpoint. Returns raw response text or raises."""
    if not NIM_API_KEY:
        raise RuntimeError("NIM_API_KEY not configured")

    img_b64 = _image_to_base64(img)
    url = f"{NIM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {NIM_API_KEY}",
        "Content-Type": "application/json",
    }

    for model_name in NIM_MODELS:
        payload = {
            "model": model_name,
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
        try:
            resp = http_requests.post(url, headers=headers, json=payload, timeout=RACE_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            logger.info("NIM model %s succeeded", model_name)
            return text
        except Exception as e:
            logger.warning("NIM model %s failed: %s", model_name, e)
    raise RuntimeError("All NIM models failed")


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
    """
    Race Gemini and NVIDIA NIM in parallel.
    First successful response wins.
    If both fail, retry with Gemini (more reliable).
    """
    prompt = _build_prompt(dict_of_vars)

    # --- Parallel race ---
    results: list[tuple[str, str]] = []  # (provider_name, response_text)
    errors: list[tuple[str, str]] = []

    def _gemini_task() -> None:
        try:
            text = _call_gemini(prompt, img)
            results.append(("gemini", text))
        except Exception as e:
            errors.append(("gemini", str(e)))

    def _nim_task() -> None:
        try:
            text = _call_nim(prompt, img)
            results.append(("nim", text))
        except Exception as e:
            errors.append(("nim", str(e)))

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        futures = [executor.submit(_gemini_task), executor.submit(_nim_task)]
        concurrent.futures.wait(futures, timeout=RACE_TIMEOUT + 1, return_when=concurrent.futures.FIRST_COMPLETED)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if results:
        provider, text = results[0]  # first completed result
        logger.info("Race won by %s", provider)
        return _parse_response(text)

    # --- Both failed — smart fallback retry ---
    # Check if Gemini is quota-exhausted (429) so we retry NIM instead
    gemini_quota_exhausted = any(
        "429" in e or "RESOURCE_EXHAUSTED" in e
        for pname, e in errors if pname == "gemini"
    )

    logger.warning("Both providers failed. Gemini: %s | NIM: %s. Retrying...",
                   dict(errors).get("gemini"), dict(errors).get("nim"))

    for attempt in range(1, FALLBACK_RETRIES + 1):
        try:
            # If Gemini is quota-exhausted, retry NIM instead
            if gemini_quota_exhausted:
                text = _call_nim(prompt, img)
                logger.info("Fallback NIM attempt %d succeeded", attempt)
            else:
                text = _call_gemini(prompt, img)
                logger.info("Fallback Gemini attempt %d succeeded", attempt)
            return _parse_response(text)
        except Exception as e:
            logger.warning("Fallback attempt %d failed: %s", attempt, e)
            if attempt < FALLBACK_RETRIES:
                time.sleep(FALLBACK_RETRY_DELAY)

    # All exhausted
    error_summary = " | ".join(f"{p}: {e}" for p, e in errors)
    raise RuntimeError(f"All AI providers failed. {error_summary}")
