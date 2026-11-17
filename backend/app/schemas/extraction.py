from typing import Optional

from pydantic import BaseModel, Field

# Categories are not hard-coded here: the active "categories" policy is the source
# of truth, and the LLM's JSON schema enum is built from it at request time
# (see app.services.extraction.build_extraction_schema). Hard-coding a separate
# list here once let the model and the policy drift apart.


class ExtractedPurchase(BaseModel):
    product_name: str = Field(
        ..., description="Produit/service vendu/acheté"
    )
    category: str = Field(
        ..., min_length=1, description="Category from the active policy"
    )
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)
    currency: str = Field(default="TND", description="TND/EUR/USD etc")
    confidence: float = Field(..., ge=0, le=1)
    notes: Optional[str] = None
