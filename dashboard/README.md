# ExpenseVoice Dashboard (MVP)

React + Vite + TypeScript dashboard for Director/Admin.

## Setup

```bash
cd dashboard
cp .env.example .env   # edit VITE_API_BASE_URL if needed
npm install
npm run dev
```

Runs at http://localhost:5173. Backend must allow CORS from this origin (already configured in backend).

## Login

- **Admin:** admin@company.com / Admin12345!
- **Director:** director@company.com / Director12345!

## Pages

- **Stats** — dashboard stats + top users + by category
- **Alerts** — list alerts, resolve (director/admin)
- **Policies** — edit limits & categories (admin only)
