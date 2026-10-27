import os
import google.generativeai as genai

api_key = os.environ.get("GOOGLE_API_KEY") 
genai.configure(api_key=api_key)

try:
    # 1. AUTO-DETECT: Scans your account for available models and picks the fastest one
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target_model = next((m for m in available_models if "flash" in m), available_models[0])
    
    # 2. JSON LOCK & PERSONA
    model = genai.GenerativeModel(
        model_name=target_model,
        system_instruction="You are an advanced automated trading and cognitive performance co-pilot. Your output must strictly be a valid JSON data structure.",
        generation_config={"response_mime_type": "application/json"} 
    )

    # 3. The daily request
    prompt = """
    Generate today's market intelligence template. 
    Include a sector health scan across the 12 market sectors and recommend 3 stock tickers for Day Trading, 3 for Swing Trading, and 3 for Long-Term Investing based on today's current market flows.
    """

    response = model.generate_content(prompt)
    print(response.text)
    
except Exception as e:
    print(f'{{"error": "Could not generate todays report. Reason: {e}"}}')
