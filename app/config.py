from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_id: str
    export_api_key: str = ""
    base_url: str = "http://localhost:8000"
    success_url: str = "http://localhost:3000/success"
    cancel_url: str = "http://localhost:3000/cancel"
    free_tier_enabled: bool = False
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
