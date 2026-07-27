# Kouttâb Stock — Frontend

SPA React 18 + TypeScript + Vite pour la gestion de stocks de l'association **Le Kouttâb**.

## Stack

- React 18 + TypeScript strict
- Vite (build tool)
- Tailwind CSS 3 + composants shadcn-style maison (Radix UI primitives)
- React Router v6
- TanStack Query v5 (data fetching & cache)
- Zustand (auth store)
- React Hook Form + Zod (formulaires)
- Recharts (graphes dashboard)
- Axios (HTTP client + interceptors JWT)
- lucide-react (icônes)

## Démarrer en dev

```bash
npm install
cp .env.example .env   # éditer si besoin
npm run dev            # http://localhost:5173
```

Le backend FastAPI doit tourner sur `http://localhost:8000`.

## Build production

```bash
npm run build
# → dist/ à uploader sur O2Switch
```

## Routes principales

- `/login`, `/signup`, `/admin-setup` (publiques)
- `/dashboard`, `/stock`, `/expenses`, `/invoices`, `/profile`
- `/expenses/validate` (Compta+)
- `/admin` (Admin+)
- `/admin/database` (Super Admin)

## Permissions

Voir `src/lib/auth.ts` pour la matrice et `CLAUDE.md` racine du projet.
