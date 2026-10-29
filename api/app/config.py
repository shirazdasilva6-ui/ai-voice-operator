from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"  # "production" makes missing secrets a startup error (fail closed)
    dashboard_token: str = ""     # bearer token for /metrics, /calls and the assistant config

    database_url: str = "postgresql://postgres:postgres@localhost:5432/operator"
    public_base_url: str = "http://localhost:8000"
    web_origin: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"

    vapi_secret: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_from: str = ""
    twilio_validate: bool = True

    calendly_token: str = ""
    calendly_event_type_uri: str = ""

    hubspot_token: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    human_cost_per_call: float = 7.00


    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


def production_problems(s: Settings) -> list[str]:
    """Settings that would leave a public endpoint unauthenticated. Empty list = safe to serve."""
    if not s.is_production:
        return []
    problems = [f"{name.upper()} is not set" for name in ("vapi_secret", "twilio_auth_token", "dashboard_token") if not getattr(s, name)]
    if not s.twilio_validate:
        problems.append("TWILIO_VALIDATE must be true")
    if s.stripe_secret_key and not s.stripe_webhook_secret:
        problems.append("STRIPE_WEBHOOK_SECRET is not set")
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
