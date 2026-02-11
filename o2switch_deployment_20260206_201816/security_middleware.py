import streamlit as st
import sqlite3
import os
from datetime import datetime, timedelta
import hashlib
import secrets

class SecurityMiddleware:
    def __init__(self):
        self.session_timeout = 3600  # 1 heure
        self.max_login_attempts = 5
        self.lockout_duration = 900  # 15 minutes
    
    def check_session_timeout(self):
        """Vérifie si la session a expiré"""
        if 'login_time' in st.session_state:
            elapsed = datetime.now().timestamp() - st.session_state.login_time
            if elapsed > self.session_timeout:
                self.logout_user()
                st.error("Session expirée. Veuillez vous reconnecter.")
                st.rerun()
    
    def check_login_attempts(self, username):
        """Vérifie les tentatives de connexion"""
        if 'login_attempts' not in st.session_state:
            st.session_state.login_attempts = {}
        
        if username in st.session_state.login_attempts:
            attempts, lockout_time = st.session_state.login_attempts[username]
            if attempts >= self.max_login_attempts:
                if datetime.now().timestamp() - lockout_time < self.lockout_duration:
                    remaining = int((self.lockout_duration - (datetime.now().timestamp() - lockout_time)) / 60)
                    st.error(f"Trop de tentatives. Compte bloqué pour {remaining} minutes.")
                    return False
                else:
                    # Reset après délai
                    del st.session_state.login_attempts[username]
        return True
    
    def record_failed_login(self, username):
        """Enregistre une tentative de connexion échouée"""
        if 'login_attempts' not in st.session_state:
            st.session_state.login_attempts = {}
        
        if username in st.session_state.login_attempts:
            attempts, _ = st.session_state.login_attempts[username]
            st.session_state.login_attempts[username] = (attempts + 1, datetime.now().timestamp())
        else:
            st.session_state.login_attempts[username] = (1, datetime.now().timestamp())
    
    def reset_login_attempts(self, username):
        """Réinitialise les tentatives de connexion après succès"""
        if 'login_attempts' in st.session_state and username in st.session_state.login_attempts:
            del st.session_state.login_attempts[username]
    
    def logout_user(self):
        """Déconnecte l'utilisateur et nettoie la session"""
        keys_to_delete = list(st.session_state.keys())
        for key in keys_to_delete:
            if key not in ['login_attempts']:  # Conserver les tentatives pour sécurité
                del st.session_state[key]
    
    def validate_file_upload(self, uploaded_file, allowed_types=None, max_size_mb=5):
        """Valide les fichiers uploadés"""
        if uploaded_file is None:
            return False, "Aucun fichier sélectionné"
        
        # Vérification taille
        if hasattr(uploaded_file, 'size') and uploaded_file.size > max_size_mb * 1024 * 1024:
            return False, f"Fichier trop volumineux (max {max_size_mb}MB)"
        
        # Vérification type
        if allowed_types:
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()
            if file_extension not in allowed_types:
                return False, f"Type de fichier non autorisé. Types acceptés: {', '.join(allowed_types)}"
        
        # Vérification contenu (basique)
        if hasattr(uploaded_file, 'getvalue'):
            content = uploaded_file.getvalue()
            # Vérification signature magique pour les images
            if file_extension in ['.jpg', '.jpeg']:
                if not content.startswith(b'\xff\xd8\xff'):
                    return False, "Fichier image invalide"
            elif file_extension == '.png':
                if not content.startswith(b'\x89PNG\r\n\x1a\n'):
                    return False, "Fichier PNG invalide"
        
        return True, "Fichier valide"
    
    def secure_database_path(self, db_name='data/stock_kouttab.db'):
        """Retourne un chemin sécurisé pour la base de données"""
        # Place la DB dans un répertoire protégé
        secure_dir = os.path.join(os.path.dirname(__file__), 'data')
        if not os.path.exists(secure_dir):
            os.makedirs(secure_dir, mode=0o700)  # Permissions restrictives
        
        return os.path.join(secure_dir, db_name)
    
    def log_security_event(self, event_type, details, user=None):
        """Enregistre un événement de sécurité"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {event_type}: {details}"
        if user:
            log_entry += f" (User: {user})"
        
        # Écrire dans un fichier de log sécurisé
        log_file = os.path.join(os.path.dirname(__file__), 'security.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
        
        # Aussi dans le logger normal
        st.session_state.get('logger', print)(f"SECURITY: {log_entry}")

# Instance globale du middleware
security = SecurityMiddleware()
