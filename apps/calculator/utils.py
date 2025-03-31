import google.generativeai as genai
import ast
import json
from PIL import  Image
from constants import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

def analyze_image(img: Image, dict_of_vars: dict):
    dict_of_vars_str = json.dumps(dict_of_vars, ensure_ascii=False)
    prompt = (
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
    
    response = model.generate_content([prompt, img])
    print("AI Response:", response.text)
    answers = []
    
    # Clean the response text
    clean_text = response.text.strip()
    if not clean_text.startswith('['):
        # Try to find the list in the response
        start = clean_text.find('[')
        if start != -1:
            clean_text = clean_text[start:]
    if not clean_text.endswith(']'):
        end = clean_text.rfind(']')
        if end != -1:
            clean_text = clean_text[:end+1]
    
    try:
        answers = ast.literal_eval(clean_text)
        if not isinstance(answers, list):
            answers = [answers] if isinstance(answers, dict) else []
    except Exception as e:
        print(f"Error parsing response: {e}")
        answers = []
    
    # Ensure each answer has the required format
    formatted_answers = []
    for answer in answers:
        if isinstance(answer, dict):
            if 'expr' in answer and 'result' in answer:
                if 'assign' not in answer:
                    answer['assign'] = False
                # Add spaces between words if they're missing
                if isinstance(answer['expr'], str):
                    answer['expr'] = ' '.join(answer['expr'].replace('_', ' ').split())
                formatted_answers.append(answer)
    
    print('Formatted answers:', formatted_answers)
    return formatted_answers