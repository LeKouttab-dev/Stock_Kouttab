import secrets
import hashlib
import sqlite3
from datetime import datetime, timedelta
from database import DATABASE_NAME
from logger_config import logger
import streamlit as st

class InvitationManager:
    def __init__(self):
        self.token_expiry_hours = 24
        self.max_attempts_per_token = 3
    
    def generate_admin_invitation(self, admin_email):
        """Génère une invitation pour le premier admin"""
        # Générer un token unique
        token = secrets.token_urlsafe(32)
        
        # Hash du token pour stockage sécurisé
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Date d'expiration
        expires_at = datetime.now() + timedelta(hours=self.token_expiry_hours)
        
        # Stocker l'invitation
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        # Créer la table si elle n'existe pas
        c.execute('''
            CREATE TABLE IF NOT EXISTS AdminInvitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        try:
            c.execute('''
                INSERT INTO AdminInvitations (email, token_hash, expires_at)
                VALUES (?, ?, ?)
            ''', (admin_email, token_hash, expires_at.isoformat()))
            
            conn.commit()
            logger.info(f"Invitation admin générée pour {admin_email}")
            conn.close()
            
            return token, expires_at
            
        except sqlite3.IntegrityError:
            conn.close()
            logger.warning(f"Invitation déjà existante pour {admin_email}")
            return None, None
    
    def validate_invitation_token(self, token, email):
        """Valide un token d'invitation"""
        if not token or not email:
            return False, "Token ou email manquant"
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, expires_at, used, attempts 
            FROM AdminInvitations 
            WHERE email = ? AND token_hash = ?
        ''', (email, token_hash))
        
        result = c.fetchone()
        conn.close()
        
        if not result:
            logger.warning(f"Tentative d'invitation invalide: {email}")
            return False, "Lien d'invitation invalide"
        
        invitation_id, expires_at, used, attempts = result
        
        # Vérifier si déjà utilisé
        if used:
            return False, "Lien d'invitation déjà utilisé"
        
        # Vérifier expiration
        if datetime.now() > datetime.fromisoformat(expires_at):
            return False, "Lien d'invitation expiré"
        
        # Vérifier tentatives
        if attempts >= self.max_attempts_per_token:
            return False, "Trop de tentatives pour ce lien"
        
        return True, "Invitation valide"
    
    def mark_invitation_used(self, token, email):
        """Marque une invitation comme utilisée"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        c.execute('''
            UPDATE AdminInvitations 
            SET used = TRUE 
            WHERE email = ? AND token_hash = ?
        ''', (email, token_hash))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Invitation utilisée pour {email}")
    
    def increment_attempts(self, token, email):
        """Incrémente le nombre de tentatives"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        c.execute('''
            UPDATE AdminInvitations 
            SET attempts = attempts + 1 
            WHERE email = ? AND token_hash = ?
        ''', (email, token_hash))
        
        conn.commit()
        conn.close()
    
    def cleanup_expired_invitations(self):
        """Nettoie les invitations expirées"""
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        
        c.execute('''
            DELETE FROM AdminInvitations 
            WHERE expires_at < ? OR used = TRUE
        ''', (datetime.now().isoformat(),))
        
        deleted = c.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Nettoyage de {deleted} invitations expirées")

# Instance globale
invitation_manager = InvitationManager()
