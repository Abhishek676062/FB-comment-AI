import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---

# 1. Initialize FastAPI app
app = FastAPI()

# 2. Set up CORS (Cross-Origin Resource Sharing)
# This allows your frontend (index.html) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# 3. Initialize Groq Client
# This requires a GROQ_API_KEY set in your .env file
try:
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        print("Error: GROQ_API_KEY environment variable not set.")
        print("Please create a .env file and add GROQ_API_KEY=your_api_key")
    client = Groq(api_key=groq_api_key)
    MODEL = 'llama-3.1-8b-instant'
except Exception as e:
    print(f"Error initializing Groq client: {e}")
    client = None

# --- Pydantic Models (Data Validation) ---

class CommentRequest(BaseModel):
    """Defines the shape of the input JSON."""
    keyword: str

class CommentResponse(BaseModel):
    """Defines the shape of the output JSON."""
    keyword: str
    generated_comments: list[str]

# --- Helper Function ---

def parse_generated_comments(text_response: str) -> list[str]:
    """
    Parses the raw text response from the LLM into a list of comments.
    Assumes comments are separated by newlines and may have numbering.
    """
    # Use regex to find lines starting with a number, a period, and a space
    # (e.g., "1. ", "2. ")
    comments = re.split(r'\n\d+\.\s*', text_response)
    
    # Clean up the list
    cleaned_comments = []
    for comment in comments:
        # Remove any leading/trailing whitespace
        c = comment.strip()
        # Remove potential numbering from the first item if split fails
        if c.startswith('1. '):
            c = c[3:]
        # Remove quotes if the model wraps comments in them
        if len(c) > 2 and c.startswith('"') and c.endswith('"'):
            c = c[1:-1]
        # Only add non-empty strings
        if c:
            cleaned_comments.append(c)
            
    # Fallback if regex split fails
    if not cleaned_comments and text_response:
        cleaned_comments = [c.strip() for c in text_response.split('\n') if c.strip()]

    return cleaned_comments or ["Sorry, I couldn't generate a comment for that."]


# --- API Endpoints ---

@app.get("/", response_class=FileResponse)
async def get_frontend():
    """
    Serves the main HTML frontend file.
    """
    return FileResponse('index.html')

@app.post("/generate_comment", response_model=CommentResponse)
async def generate_comment(request: CommentRequest):
    """
    The main endpoint to generate comments based on a keyword.
    """
    if not client:
        raise HTTPException(
            status_code=500, 
            detail="Groq client is not initialized. Check GROQ_API_KEY."
        )
        
    keyword = request.keyword
    
    # This prompt is designed to get a list of comments
    system_prompt = "You are an expert at writing short, natural, and positive Facebook comments."
    user_prompt = f"""
    Generate 3 unique, short, and natural-sounding Facebook comments 
    about the keyword: "{keyword}"

    Guidelines:
    - Sound human, like a real person would write.
    - Keep them positive and engaging.
    - Each comment should be 1-2 sentences.
    - Return *only* the comments, each on a new line, starting with '1. ', '2. ', and '3. '.
    - Do not add any extra text, introduction, or conclusion.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL,
            temperature=0.7, # Controls creativity
            max_tokens=150,
        )
        
        raw_response = chat_completion.choices[0].message.content
        comments = parse_generated_comments(raw_response)
        
        return CommentResponse(keyword=keyword, generated_comments=comments)

    except Exception as e:
        print(f"Error calling Groq API: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating comment: {e}")

# To run this app:
# 1. Make sure you have a .env file with your GROQ_API_KEY
# 2. Run in your terminal: uvicorn main:app --reload