"""
ExpenseVoice AI - Backend API
Point d'entrée principal de l'application FastAPI
"""

from fastapi import FastAPI

app = FastAPI(
    title="ExpenseVoice AI",
    description="API pour la gestion des ventes par reconnaissance vocale et OCR",
    version="0.1.0",
)


@app.get("/")
def root():
    """Endpoint racine."""
    return {"status": "ok", "service": "ExpenseVoice AI"}


@app.get("/health")
def health_check():
    """Health check pour monitoring et déploiement."""
    return {"status": "healthy"}
