#!/usr/bin/env python3
"""
Version test minimaliste pour diagnostiquer le problème
"""

import os
import sys

print("🚀 Test de l'application Gestion Stock Kouttab")
print("=" * 50)

# Test des variables environnement
print("Variables environnement :")
print(f"ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'NON DÉFINI')}")
print(f"DATABASE_PATH: {os.environ.get('DATABASE_PATH', 'NON DÉFINI')}")
print(f"DOMAIN_URL: {os.environ.get('DOMAIN_URL', 'NON DÉFINI')}")
print()

# Test des imports
try:
    import streamlit as st
    print("✅ Streamlit importé")
except Exception as e:
    print(f"❌ Erreur Streamlit: {e}")
    sys.exit(1)

try:
    import pandas as pd
    print("✅ Pandas importé")
except Exception as e:
    print(f"❌ Erreur Pandas: {e}")

try:
    import emoji
    print("✅ Emoji importé")
except Exception as e:
    print(f"❌ Erreur Emoji: {e}")

try:
    import bcrypt
    print("✅ Bcrypt importé")
except Exception as e:
    print(f"❌ Erreur Bcrypt: {e}")

print()

# Test base de données
try:
    from database import init_db, DATABASE_PATH
    print(f"✅ Database importé, chemin: {DATABASE_PATH}")
    
    # Test initialisation
    init_db()
    print("✅ Base de données initialisée")
except Exception as e:
    print(f"❌ Erreur base de données: {e}")

print()
print("🎉 Test terminé avec succès !")

# Si tout va bien, lancez l'application réelle
if __name__ == "__main__":
    print("Lancement de l'application complète...")
    try:
        from app import main
        main()
    except Exception as e:
        print(f"❌ Erreur application complète: {e}")
        import traceback
        traceback.print_exc()
