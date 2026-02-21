# ExpenseVoice AI

Système de saisie des ventes par reconnaissance vocale et OCR pour une entreprise industrielle de volaille.

## Contexte

Entreprise de production et vente de poulets. Les employés enregistrent chaque vente (conteneurs, matériel, etc.). Les directeurs et managers suivent les ventes et achats en temps réel pour limiter les pertes et la fraude.

## Objectifs

- Saisie des ventes par **voix** (reconnaissance vocale)
- Upload optionnel de **photo de facture** (OCR)
- Extraction structurée par IA : produit, quantité, prix, total, catégorie
- Stockage en **PostgreSQL**
- Tableaux de bord et statistiques pour Manager et Directeur
- Détection d’**anomalies** et transactions suspectes

## Utilisateurs

| Rôle      | Description                          |
|-----------|--------------------------------------|
| Employee  | Enregistre les ventes (voix, photo)  |
| Manager   | Consulte les stats, valide les ventes|
| Director  | Vue globale, gestion des utilisateurs|

~20 utilisateurs.

## Stack technique

| Composant | Technologie                          |
|-----------|--------------------------------------|
| Backend   | Python 3.11, FastAPI                 |
| Base de données | PostgreSQL                    |
| ORM       | SQLAlchemy 2.0                       |
| Speech-to-text | Whisper (faster-whisper)        |
| LLM (dev) | Qwen2.5 via Ollama                   |
| LLM (prod)| OpenAI API                           |
| Mobile    | Flutter (ou React Native)            |
| Dashboard | React                                |
| Déploiement | Docker, Docker Compose            |
| Hébergement | VPS (DigitalOcean, Hetzner, AWS)   |

## Structure du projet

```
expensevoice-ai/
├── backend/     # API FastAPI, logique métier, pipeline IA
├── mobile/      # Application mobile (Flutter)
├── dashboard/   # Interface web de gestion (React)
├── infra/       # Docker, scripts de déploiement
└── README.md
```

## Déploiement

1. **Développement** : environnement local
2. **Production** : backend hébergé sur VPS ; application mobile installée sur les téléphones des employés

## Exigences

- Architecture propre et modulaire
- Environnements séparés (dev / prod)
- Authentification JWT
- Contrôle d’accès par rôles (RBAC)
- Logging et gestion des erreurs
- Documentation de l’API

---

*ExpenseVoice AI — Technical Lead Architecture v0.1*
