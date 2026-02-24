import secrets
import hashlib
from datetime import datetime, timedelta

import streamlit as st

from database import get_db_connection
from logger_config import logger


class InvitationManager:
    def __init__(self):
        self.token_expiry_hours = 24
        self.max_attempts_per_token = 3

    def _ensure_table(self, conn):
        """Crée la table AdminInvitations si nécessaire (MySQL)."""
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS AdminInvitations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                attempts INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def generate_admin_invitation(self, admin_email):
        """Génère une invitation pour le premier admin (stockée en base MySQL)."""
        conn = get_db_connection()
        if conn is None:
            st.error("Connexion à la base de données indisponible. Impossible de générer l'invitation.")
            return None, None

        # Générer un token unique
        token = secrets.token_urlsafe(32)

        # Hash du token pour stockage sécurisé
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Date d'expiration
        expires_at = datetime.now() + timedelta(hours=self.token_expiry_hours)

        c = conn.cursor()
        self._ensure_table(conn)

        try:
            c.execute(
                """
                INSERT INTO AdminInvitations (email, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (admin_email, token_hash, expires_at),
            )
            conn.commit()
            logger.info(f"Invitation admin générée pour {admin_email}")
            return token, expires_at
        except Exception as e:
            # Conflit de clé unique (invitation déjà existante)
            logger.warning(f"Invitation déjà existante pour {admin_email} ou erreur: {e}")
            return None, None

    def validate_invitation_token(self, token, email):
        """Valide un token d'invitation"""
        if not token or not email:
            return False, "Token ou email manquant"

        conn = get_db_connection()
        if conn is None:
            st.error("Connexion à la base de données indisponible. Impossible de valider l'invitation.")
            return False, "Erreur de connexion à la base"

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        c = conn.cursor()
        self._ensure_table(conn)
        c.execute(
            """
            SELECT id, expires_at, used, attempts 
            FROM AdminInvitations 
            WHERE email = %s AND token_hash = %s
            """,
            (email, token_hash),
        )

        result = c.fetchone()

        if not result:
            logger.warning(f"Tentative d'invitation invalide: {email}")
            return False, "Lien d'invitation invalide"

        invitation_id, expires_at, used, attempts = result

        # Vérifier si déjà utilisé
        if used:
            return False, "Lien d'invitation déjà utilisé"

        # Vérifier expiration
        if datetime.now() > expires_at:
            return False, "Lien d'invitation expiré"

        # Vérifier tentatives
        if attempts >= self.max_attempts_per_token:
            return False, "Trop de tentatives pour ce lien"

        return True, "Invitation valide"

    def mark_invitation_used(self, token, email):
        """Marque une invitation comme utilisée"""
        conn = get_db_connection()
        if conn is None:
            st.error("Connexion à la base de données indisponible. Impossible de marquer l'invitation comme utilisée.")
            return

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        c = conn.cursor()
        self._ensure_table(conn)
        c.execute(
            """
            UPDATE AdminInvitations 
            SET used = TRUE 
            WHERE email = %s AND token_hash = %s
            """,
            (email, token_hash),
        )
        conn.commit()
        logger.info(f"Invitation utilisée pour {email}")

    def increment_attempts(self, token, email):
        """Incrémente le nombre de tentatives"""
        conn = get_db_connection()
        if conn is None:
            st.error("Connexion à la base de données indisponible. Impossible de mettre à jour les tentatives.")
            return

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        c = conn.cursor()
        self._ensure_table(conn)
        c.execute(
            """
            UPDATE AdminInvitations 
            SET attempts = attempts + 1 
            WHERE email = %s AND token_hash = %s
            """,
            (email, token_hash),
        )
        conn.commit()

    def cleanup_expired_invitations(self):
        """Nettoie les invitations expirées"""
        conn = get_db_connection()
        if conn is None:
            logger.error("Connexion à la base de données indisponible. Impossible de nettoyer les invitations.")
            return

        c = conn.cursor()
        self._ensure_table(conn)
        c.execute(
            """
            DELETE FROM AdminInvitations 
            WHERE expires_at < NOW() OR used = TRUE
            """
        )

        deleted = c.rowcount
        conn.commit()

        if deleted > 0:
            logger.info(f"Nettoyage de {deleted} invitations expirées")

# Instance globale
invitation_manager = InvitationManager()
