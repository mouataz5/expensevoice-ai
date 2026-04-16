import os


def get_default_limits_policy() -> dict:
    return {
        "max_per_purchase": float(os.getenv("MAX_PER_PURCHASE", "500")),
        "daily_limit_default": float(os.getenv("DAILY_LIMIT_DEFAULT", "1500")),
    }


def get_default_categories_policy() -> dict:
    raw = os.getenv(
        "ALLOWED_CATEGORIES",
        "vente_poussins,vente_nourriture,charge_fixe_location,charge_fixe_salaires,charge_fixe_abonnement,charge_variable_eau,charge_variable_electricite,charge_variable_medicaments,charge_variable_transport,charge_variable_autre",
    )
    allowed = [x.strip() for x in raw.split(",") if x.strip()]
    return {"allowed": allowed}


def get_default_finance_taxonomy_policy() -> dict:
    return {
        "products": ["poussins", "nourriture"],
        "fixed_expense_categories": [
            "charge_fixe_location",
            "charge_fixe_salaires",
            "charge_fixe_abonnement",
        ],
        "variable_expense_categories": [
            "charge_variable_eau",
            "charge_variable_electricite",
            "charge_variable_medicaments",
            "charge_variable_transport",
            "charge_variable_autre",
        ],
        "sales_categories": [
            "vente_poussins",
            "vente_nourriture",
        ],
    }


def get_default_approval_workflow_policy() -> dict:
    return {
        "require_admin_approval": True,
        "allow_director_approval": True,
        "monthly_closing_enabled": True,
        "monthly_closing_day": 28,
    }
