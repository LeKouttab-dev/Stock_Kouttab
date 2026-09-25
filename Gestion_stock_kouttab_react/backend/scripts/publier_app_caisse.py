#!/usr/bin/env python
"""Publie l'APK de la tablette de caisse depuis le VPS.

A lancer DANS le conteneur `api`, ou le dossier `uploads` est monte :

    docker compose cp buvette.apk api:/tmp/buvette.apk
    docker compose exec -T api python scripts/publier_app_caisse.py /tmp/buvette.apk 3 0.3.0

Pourquoi ce script plutot qu'une copie directe dans le volume : ce que l'API sert
n'est pas seulement l'APK, c'est **l'APK plus son manifeste** — numero de
version, nom, empreinte SHA-256. Un APK depose seul ne serait servi a personne,
et rien ne le signalerait ; une empreinte recopiee de travers ferait refuser
l'installation par la tablette, sans message non plus. Ici l'empreinte est
calculee, et le manifeste ecrit apres le fichier.

Passer par le conteneur evite aussi de deviner le chemin du volume sur l'hote
(`/var/lib/docker/volumes/...`), qui change avec le nom du projet et appartient
a root, alors que les fichiers doivent appartenir a l'utilisateur `kouttab`.

L'ecran *Stock buvette > Application tablette* fait exactement la meme chose
depuis un navigateur. Les deux chemins aboutissent au meme endroit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# Le script vit dans `backend/scripts/`, l'application dans `backend/app/`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import caisse_app  # noqa: E402


def _arguments() -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("apk", help="Chemin de l'APK a publier.")
    analyseur.add_argument(
        "version_code",
        nargs="?",
        type=int,
        help="versionCode Android. La tablette n'installe que s'il depasse le sien.",
    )
    analyseur.add_argument("version_name", nargs="?", help="Nom de version, ex. 0.3.0.")
    analyseur.add_argument(
        "--depuis-json",
        metavar="FICHIER",
        help=(
            "Lit `version_code` et `version_name` dans ce JSON plutot que sur la "
            "ligne de commande — pour une chaine de compilation qui produit deja "
            "un descripteur a cote de l'APK."
        ),
    )
    return analyseur.parse_args()


def main() -> int:
    args = _arguments()

    chemin = Path(args.apk)
    if not chemin.is_file():
        print(f"ECHEC : introuvable — {chemin}", file=sys.stderr)
        return 1

    code, nom = args.version_code, args.version_name
    if args.depuis_json:
        try:
            donnees = json.loads(Path(args.depuis_json).read_text(encoding="utf-8"))
            code = int(donnees["version_code"])
            nom = str(donnees["version_name"])
        except (OSError, ValueError, KeyError) as exc:
            print(f"ECHEC : descripteur illisible — {exc}", file=sys.stderr)
            return 1

    if code is None or not nom:
        print(
            "ECHEC : donnez `version_code` et `version_name`, ou --depuis-json.",
            file=sys.stderr,
        )
        return 1

    try:
        version = caisse_app.publier(
            chemin.read_bytes(),
            version_code=code,
            version_name=nom.strip(),
            depose_le=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    except Exception as exc:  # noqa: BLE001 - un script, pas une API
        print(f"ECHEC : {exc}", file=sys.stderr)
        return 1

    print("Application de caisse publiee.")
    print(f"  version      : {version.version_name} (code {version.version_code})")
    print(f"  taille       : {version.taille} octets")
    print(f"  sha256       : {version.sha256}")
    print(f"  fichier servi: {caisse_app.chemin_apk()}")
    print()
    print("Les tablettes l'installeront au repos, dans la demi-heure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
