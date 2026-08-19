from pydantic_settings import BaseSettings


class Config(BaseSettings):
    GEMINI_API_KEY: str
    EXA_API_KEY: str
    OPENAI_API_KEY: str

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/dbname"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"  # Keep for backward compatibility if needed
    REDIS_PORT: int = 6379  # Keep for backward compatibility if needed

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Config()
