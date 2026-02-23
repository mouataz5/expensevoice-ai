from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "vente_poulet", "achat_aliment", "materiel", "transport", "autre"
]


class ExtractedPurchase(BaseModel):
    product_name: str = Field(
        ..., description="Produit/service vendu/acheté"
    )
    category: Category = Field(
        ..., description="Catégorie normalisée"
    )
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)
    currency: str = Field(default="TND", description="TND/EUR/USD etc")
    confidence: float = Field(..., ge=0, le=1)
    notes: Optional[str] = None
