from pydantic import BaseModel


class SettingsOut(BaseModel):
    company_name: str
    currency: str
    logo_url: str | None
    default_limits: dict  # e.g. {"max_per_purchase": 500, "daily_limit_default": 1500}
    working_days: list  # e.g. [0, 1, 2, 3, 4] for Mon–Fri (ISO weekday)

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    company_name: str | None = None
    currency: str | None = None
    logo_url: str | None = None
    default_limits: dict | None = None
    working_days: list | None = None
