import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure the API key
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Initialize the system instruction
system_instruction = """
You are an expert Senior AI Architect and RPA Log Analyzer. 
Your task is to analyze the provided RPA logs and extract the following information in a structured format:
1. Root Cause: Explain why the error occurred based on the log details.
2. SAP Selector fixes: Suggest specific fixes or adjustments for any SAP selectors mentioned in the logs.
3. Classification: Classify the error strictly as either 'Business Exception' or 'System Exception'.
"""

def analyze_rpa_logs(log_text: str) -> str:
    """Sends RPA log text to Gemini 1.5 Flash for analysis."""
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set or empty.")
        
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        response = model.generate_content(log_text)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Failed to analyze logs with Gemini: {str(e)}")
