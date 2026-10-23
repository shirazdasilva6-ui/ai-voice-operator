from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # Per-country monthly price and one-off setup price, as JSON: {"US": "price_...", "GB": "price_..."}
    stripe_price_ids: dict[str, str] = {}
    stripe_setup_price_ids: dict[str, str] = {}

    vapi_api_key: str = ""
    # Twilio regulatory bundle + address per country, required to buy GB/AU numbers: {"GB": "BU..."}
    twilio_bundle_sids: dict[str, str] = {}
    twilio_address_sids: dict[str, str] = {}

    resend_api_key: str = ""
    resend_from: str = "Voice Operator <onboarding@example.com>"
    ops_email: str = ""

    human_cost_per_call: float = 7.00


@lru_cache
def get_settings() -> Settings:
    return Settings()
