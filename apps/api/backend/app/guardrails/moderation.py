from openai import AsyncOpenAI
from fastapi import HTTPException
from backend.app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def check_moderation(text: str) -> None:
    """
    Checks the query against openai's moderation api.
    Raises a 400 HTTPException if the content is flagged.
    """
    try:
        response = await client.moderations.create(input=text)
        result = response.results[0]
        
        if result.flagged:
            flagged_categories = [
                cat for cat, is_flagged in result.categories.model_dump().items() if is_flagged
            ]
            print(f"Moderation flagged query. Categories: {flagged_categories}")
            raise HTTPException(
                status_code=400, 
                detail="Your query was flagged by our safety moderation system."
            )
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Moderation API failed: {e}. Failing open.")
