#!/usr/bin/env python3
"""
Générateur de SECRET_KEY sécurisée pour Streamlit
Crée une clé aléatoire de 64 caractères
"""

import secrets
import string

def generate_secret_key():
    """Génère une SECRET_KEY sécurisée"""
    # Créer une clé de 64 caractères avec lettres, chiffres et symboles
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    secret_key = ''.join(secrets.choice(alphabet) for _ in range(64))
    
    return secret_key

def main():
    print("GENERATEUR DE SECRET_KEY STREAMLIT")
    print("=" * 50)
    
    # Générer la clé
    secret_key = generate_secret_key()
    
    print(f"SECRET_KEY generee :")
    print(f"{secret_key}")
    print()
    print("Copiez cette clé dans votre configuration :")
    print("1. O2Switch : Variable d'environnement SECRET_KEY")
    print("2. Local : .streamlit/secrets.toml")
    print()
    print("ATTENTION : CONSERVEZ CETTE CLE SECRETE !")
    print("   Ne la partagez jamais et ne la mettez pas dans Git !")
    
    return secret_key

if __name__ == "__main__":
    main()
