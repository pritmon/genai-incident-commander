from fastapi import FastAPI, File, UploadFile, HTTPException, status
from pydantic import BaseModel
from app import engine

app = FastAPI(
    title="RPA Log Analyzer API",
    description="API for analyzing RPA logs using Gemini 1.5 Flash",
    version="1.0.0"
)

class AnalysisResponse(BaseModel):
    analysis: str

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_log_file(file: UploadFile = File(...)):
    """
    Accepts an uploaded .txt file containing RPA logs and returns an analysis based on
    Root Cause, SAP Selector fixes, and Exception Classification.
    """
    if file.content_type != "text/plain" and not file.filename.endswith(".txt"):
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Only .txt files are supported."
         )
         
    try:
        content = await file.read()
        log_text = content.decode("utf-8")
    except Exception:
        raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Failed to read or decode the uploaded file. Ensure it is a valid text file."
         )
         
    if not log_text.strip():
        raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="The uploaded file is empty."
         )
         
    try:
        analysis_result = engine.analyze_rpa_logs(log_text)
        return {"analysis": analysis_result}
    except Exception as e:
        # Catch API failures or configuration issues
        raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Error generating analysis: {str(e)}"
         )

@app.get("/")
def read_root():
    return {"message": "Welcome to the RPA Log Analyzer API. Send a POST request with a .txt file to /analyze."}
