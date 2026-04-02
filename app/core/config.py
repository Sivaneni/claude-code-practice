import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    openweather_base_url: str = "https://api.openweathermap.org/data/2.5/weather"
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "change-me-in-production-use-a-strong-secret"  # nosec
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )


settings = Settings()
