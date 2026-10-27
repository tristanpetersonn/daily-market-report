import os
import google.generativeai as genai

# 1. SECURITY: Pulls your API key from a secure, hidden spot on your computer
# (You will need to save your key to your computer's "Environment Variables" first)
api_key = os.environ.get("GOOGLE_API_KEY") 
genai.configure(api_key=api_key)

# 2. JSON LOCK & PERSONA: Sets your exact rules and forces pure data output
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="You are an advanced automated trading and cognitive performance co-pilot. Your output must strictly be a valid JSON data structure.",
    generation_config={"response_mime_type": "application/json"} # This is the magic lock
)

# The daily request
prompt = """
Generate today's market intelligence template. 
Include a sector health scan across the 12 market sectors and recommend 3 stock tickers for Day Trading, 3 for Swing Trading, and 3 for Long-Term Investing based on today's current market flows.
"""

# 3. SAFETY NET: Prevents the whole system from crashing if there is a glitch
try:
    response = model.generate_content(prompt)
    
    # This will now print a perfectly clean, machine-readable JSON payload
    print(response.text)
    
except Exception as e:
    # If the internet drops, it hands Muse a clean error instead of exploding
    print(f'{{"error": "Could not generate todays report. Reason: {e}"}}')
