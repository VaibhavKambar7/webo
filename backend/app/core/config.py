import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    EXA_API_KEY = os.getenv("EXA_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    if not EXA_API_KEY:
        raise ValueError("EXA_API_KEY is not set")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set")


settings = Config()
