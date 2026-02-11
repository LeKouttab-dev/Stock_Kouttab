import bcrypt
import secrets
import re
import hashlib

def hash_password_secure(password):
    """Hachage sécurisé avec bcrypt et sel"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password_secure(hashed_password, provided_password):
    """Vérification sécurisée du mot de passe avec compatibilité SHA256"""
    try:
        # Essayer d'abord avec bcrypt (nouveaux comptes)
        return bcrypt.checkpw(provided_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except (ValueError, TypeError):
        # Si erreur, essayer avec SHA256 (anciens comptes)
        try:
            # Vérifier si c'est un hash SHA256 (64 caractères hexadécimaux)
            if len(hashed_password) == 64 and all(c in '0123456789abcdefABCDEF' for c in hashed_password):
                sha256_hash = hashlib.sha256(provided_password.encode()).hexdigest()
                return sha256_hash == hashed_password.lower()
            return False
        except:
            return False

def validate_email(email):
    """Validation format email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username):
    """Validation nom d'utilisateur"""
    if len(username) < 3 or len(username) > 20:
        return False
    return re.match(r'^[a-zA-Z0-9_]+$', username) is not None

def sanitize_input(input_string):
    """Nettoyage des entrées utilisateur"""
    if not input_string:
        return ""
    # Supprime les caractères dangereux
    dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
    for char in dangerous_chars:
        input_string = input_string.replace(char, '')
    return input_string.strip()

def generate_session_token():
    """Génère un token de session sécurisé"""
    return secrets.token_urlsafe(32)
