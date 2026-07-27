# Kouttab Stock — React Edition

Réécriture moderne de l'application de gestion de stocks de l'institut **Le Kouttâb**.
Stack : **React 18 + TypeScript + Vite** (frontend) · **FastAPI + SQLAlchemy 2** (backend) · **MySQL O2Switch** (DB conservée).

---

## 📚 Documents

| Fichier | Pour quoi |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Guide technique complet (à lire avant tout dev avec un LLM) |
| [`prd.md`](./prd.md) | Product Requirements Document |
| [`memory.md`](./memory.md) | Décisions stables, contraintes, hors-scope |
| [`prd-guide.md`](./prd-guide.md) | Guide générique de rédaction de PRD (référence) |

---

## 🚀 Quick start (dev)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                # Windows ; sur Unix : source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # puis remplir DB_*, JWT_SECRET_KEY, SMTP_*
uvicorn app.main:app --reload --port 8000

# Frontend (dans un autre terminal)
cd frontend
npm install
copy .env.example .env                # VITE_API_URL=http://localhost:8000/api/v1
npm run dev                           # http://localhost:5173
```

---

## 🏗️ Build production

```bash
# Frontend
cd frontend
npm install
npm run build                         # → frontend/dist/
```

---

## 🚢 Déploiement O2Switch (résumé)

1. Build frontend localement (`npm run build`).
2. Upload `frontend/dist/*` → `/www/stock.lekouttab.fr/`
3. Upload `backend/` → `/www/stock.lekouttab.fr/backend/`
4. Upload le `.htaccess` racine de ce dossier → `/www/stock.lekouttab.fr/.htaccess`
5. Configurer cPanel → Setup Python App :
   - Python **3.11**
   - Application root : `/www/stock.lekouttab.fr/backend`
   - Startup file : `passenger_wsgi.py`
6. SSH : `pip install -r backend/requirements.txt`
7. Renseigner les variables d'environnement (`.env` ou cPanel UI)
8. Redémarrer : `touch /www/stock.lekouttab.fr/backend/tmp/restart.txt`

Détails complets : voir [`CLAUDE.md`](./CLAUDE.md) §10.

---

## 📂 Structure

```
Gestion_stock_kouttab_react/
├── CLAUDE.md / prd.md / memory.md / prd-guide.md
├── README.md
├── .gitignore
├── .htaccess                  # racine production O2Switch (SPA fallback + proxy /api)
├── backend/                   # FastAPI app
└── frontend/                  # Vite + React SPA
```

---

## 🔐 Comptes initiaux

### 🚧 Pour le développement / test (temporaire)

```bash
cd backend
python scripts/seed_super_admin.py
```

Crée un compte par défaut : **username=`admin`** / **password=`Admin1234!`** (à changer dans l'app dès la première connexion).

⚠️ **À NE PAS UTILISER EN PRODUCTION.** Voir [`CLAUDE.md`](./CLAUDE.md) §11.1 pour la procédure cible (script générant une invitation à usage unique = "Option A").

### ✅ Création d'admins suivants (flow normal)

Une fois le premier Super Admin connecté :
1. Page Admin → "Inviter un nouvel admin" (`POST /api/v1/invitations`)
2. L'invité reçoit un email avec un lien sécurisé (token 24 h, max 3 essais)
3. Il clique → page `/admin-setup` → choisit username + mot de passe
4. Compte créé, l'invité est connecté direct

---

## 🧪 Tests

```bash
cd backend
pytest
```

---

## 🤝 Contribuer

Lire `CLAUDE.md` puis `memory.md` avant toute modification. Les conventions y sont documentées (formatage, naming, sécurité, permissions par rôle).
