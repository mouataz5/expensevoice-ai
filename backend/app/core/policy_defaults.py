import os


def get_default_limits_policy() -> dict:
    return {
        "max_per_purchase": float(os.getenv("MAX_PER_PURCHASE", "500")),
        "daily_limit_default": float(os.getenv("DAILY_LIMIT_DEFAULT", "1500")),
    }


def get_default_categories_policy() -> dict:
    raw = os.getenv(
        "ALLOWED_CATEGORIES",
        "vente_poulet,achat_aliment,materiel,transport,autre",
    )
    allowed = [x.strip() for x in raw.split(",") if x.strip()]
    return {"allowed": allowed}
