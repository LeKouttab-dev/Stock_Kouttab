# Kouttâb Stock

Application de gestion des stocks, notes de frais et factures de l'institut
associatif **Le Kouttâb**.

L'application vit dans **[`Gestion_stock_kouttab_react/`](./Gestion_stock_kouttab_react/)** :

- **Frontend** : React 18 + TypeScript (Vite), Tailwind CSS, TanStack Query, Zustand
- **Backend** : FastAPI, SQLAlchemy 2, MySQL (PyMySQL), JWT
- **Hébergement** : O2Switch (cPanel + Passenger) — `stock.lekouttab.fr`

Voir [`Gestion_stock_kouttab_react/README.md`](./Gestion_stock_kouttab_react/README.md)
pour le démarrage rapide, et [`CLAUDE.md`](./Gestion_stock_kouttab_react/CLAUDE.md)
pour la documentation technique complète.

---

## Fichiers conservés à la racine

| Fichier | Rôle |
|---|---|
| `create_mysql_structure.sql` | Schéma MySQL de référence de la base de production |
| `.htaccess` | Configuration Apache **actuellement en production** : redirection vers Streamlit Cloud. À remplacer par `Gestion_stock_kouttab_react/.htaccess` lors de la bascule. |

## Version historique (Streamlit)

Une première version de l'application, écrite en **Streamlit/Python**, occupait
la racine de ce dépôt. Elle a été remplacée par la version React/FastAPI puis
retirée de l'arborescence.

Elle reste consultable :

```bash
git checkout legacy-streamlit     # tag d'archive
git checkout archive/streamlit    # branche d'archive
```

Aucune fonctionnalité n'a été perdue : la couverture a été vérifiée fonction par
fonction avant retrait (stock, notes de frais, factures, administration,
export/import de la base, envois d'e-mails).

> ⚠️ Les commits antérieurs à ce retrait contiennent des identifiants de
> production (mot de passe SMTP, `SECRET_KEY`, mot de passe d'application Gmail).
> Ces secrets sont à considérer comme compromis et doivent être révoqués :
> retirer les fichiers du suivi ne les efface pas de l'historique.
