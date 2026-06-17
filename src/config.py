import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Paths
DB_DIR = os.getenv("VECTOR_DB_DIR", os.path.join(BASE_DIR, "data", "vector_db"))
PARSED_DIR = os.path.join(BASE_DIR, "data", "parsed")

# Vector DB Configuration
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "mutual_funds_faq")

# LLM Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Allowed Schemes (in-scope)
IN_SCOPE_SCHEMES = [
    "HDFC Mid-Cap Opportunities Fund",
    "HDFC Top 100 Fund",
    "HDFC Small Cap Fund",
    "HDFC Gold ETF Fund of Fund",
    "HDFC Defence Fund"
]

def check_config():
    """
    Validates configuration settings and logs warnings for missing values.
    """
    if not GROQ_API_KEY:
        print("[WARNING] GROQ_API_KEY is not set. LLM-based classification and generation will be unavailable. Please set it in your .env file.")
