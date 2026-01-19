import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime
import os
from email_utils import send_alert_email

# --- Configuration ---
DATABASE_NAME = 'stock_kouttab.db'
UPLOADS_DIR = 'uploads'

# --- Fonctions de Hachage ---
import hashlib
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_password_hash, provided_password):
    return stored_password_hash == hash_password(provided_password)

# --- Fonctions de Base de Données ---
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS Stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE, categorie TEXT NOT NULL,
            quantite INTEGER NOT NULL, seuil_alerte INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '📦',
            alert_sent BOOLEAN NOT NULL DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS Admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
            role TEXT NOT NULL, validation_status TEXT NOT NULL DEFAULT 'pending',
            nom TEXT, prenom TEXT, email TEXT, telephone TEXT, rib TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS NotesDeFrais (
            id INTEGER PRIMARY KEY AUTOINCREMENT, id_user INTEGER NOT NULL,
            date_depense TEXT NOT NULL, rattachement TEXT NOT NULL, fournisseur TEXT,
            nature_charge TEXT, montant REAL NOT NULL, commentaires TEXT,
            remboursement_deja_emis REAL DEFAULT 0, remise REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'En attente', commentaires_compta TEXT,
            date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_user) REFERENCES Admins (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS FichiersNotesDeFrais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_note_de_frais INTEGER NOT NULL,
            nom_fichier TEXT NOT NULL,
            FOREIGN KEY (id_note_de_frais) REFERENCES NotesDeFrais (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS StockModifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_user INTEGER NOT NULL,
            id_stock INTEGER NOT NULL,
            quantite_actuelle INTEGER NOT NULL,
            quantite_demandee INTEGER NOT NULL,
            date_demande TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'En attente',
            FOREIGN KEY (id_user) REFERENCES Admins (id),
            FOREIGN KEY (id_stock) REFERENCES Stock (id)
        )
    ''')
    c.execute("SELECT * FROM Admins WHERE role = 'Super Admin'")
    if c.fetchone() is None:
        c.execute("INSERT INTO Admins (username, password_hash, role, validation_status, nom, prenom, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', hash_password('kouttab_admin'), 'Super Admin', 'active', 'Admin', 'Principal', 'admin@example.com'))
    conn.commit()
    conn.close()

# --- Fonctions Utilisateurs (Admins) ---
def get_admin_benevoles_emails():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT email FROM Admins WHERE role IN ('AdminBenevoles', 'Super Admin') AND email IS NOT NULL")
    emails = [row[0] for row in c.fetchall()]
    conn.close()
    return emails

def create_pending_admin(username, password, role, nom, prenom, email, telephone):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO Admins (username, password_hash, role, nom, prenom, email, telephone, validation_status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
                  (username, hash_password(password), role, nom, prenom, email, telephone))
        conn.commit()
        st.success("Votre demande de compte a été envoyée.")
    except sqlite3.IntegrityError:
        st.toast(f"❌ Ce nom d'utilisateur existe déjà.", icon='🚨')
    conn.close()

def get_user(username):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT id, password_hash, role, validation_status FROM Admins WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result

def get_all_users(current_user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    df = pd.read_sql_query("SELECT id, username, nom, prenom, role FROM Admins WHERE id != ?", conn, params=(current_user_id,))
    conn.close()
    return df

def update_user_role(user_id, new_role):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE Admins SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()

def get_user_profile(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT nom, prenom, email, telephone, rib FROM Admins WHERE id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_user_profile(user_id, nom, prenom, email, telephone, rib):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE Admins SET nom=?, prenom=?, email=?, telephone=?, rib=? WHERE id=?",
              (nom, prenom, email, telephone, rib, user_id))
    conn.commit()
    conn.close()

def get_pending_admins():
    conn = sqlite3.connect(DATABASE_NAME)
    df = pd.read_sql_query("SELECT id, username, role FROM Admins WHERE validation_status = 'pending'", conn)
    conn.close()
    return df

def update_validation_status(admin_id, new_status):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE Admins SET validation_status = ? WHERE id = ?", (new_status, admin_id))
    conn.commit()
    conn.close()

def delete_admin(admin_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM Admins WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()

# --- Fonctions Notes de Frais ---
def add_expense(user_id, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise, uploaded_files):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO NotesDeFrais 
        (id_user, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remboursement_deja_emis, remise) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise))
    
    note_id = c.lastrowid

    if uploaded_files:
        for uploaded_file in uploaded_files:
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}_{uploaded_file.name}"
            filepath = os.path.join(UPLOADS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(uploaded_file.getbuffer())
            c.execute("INSERT INTO FichiersNotesDeFrais (id_note_de_frais, nom_fichier) VALUES (?, ?)", (note_id, filename))

    conn.commit()
    conn.close()

def get_files_for_expense(expense_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT nom_fichier FROM FichiersNotesDeFrais WHERE id_note_de_frais = ?", (expense_id,))
    results = c.fetchall()
    conn.close()
    return [row[0] for row in results]

def delete_expense(expense_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    
    files_to_delete = get_files_for_expense(expense_id)
    
    for filename in files_to_delete:
        filepath = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            
    c.execute("DELETE FROM FichiersNotesDeFrais WHERE id_note_de_frais = ?", (expense_id,))
    c.execute("DELETE FROM NotesDeFrais WHERE id = ?", (expense_id,))
    
    conn.commit()
    conn.close()

def update_expense_details(expense_id, date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE NotesDeFrais SET
        date_depense = ?, rattachement = ?, fournisseur = ?, nature_charge = ?, montant = ?, 
        commentaires = ?, remboursement_deja_emis = ?, remise = ?
        WHERE id = ?
    """, (date_depense, rattachement, fournisseur, nature_charge, montant, commentaires, remb_emis, remise, expense_id))
    conn.commit()
    conn.close()

def update_expense_by_accountant(expense_id, new_status, new_comment):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE NotesDeFrais SET status = ?, commentaires_compta = ? WHERE id = ?", (new_status, new_comment, expense_id))
    conn.commit()
    conn.close()

def get_expenses_by_user(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    df = pd.read_sql_query("SELECT * FROM NotesDeFrais WHERE id_user = ? ORDER BY date_soumission DESC", conn, params=(user_id,))
    conn.close()
    return df

def get_all_expenses():
    conn = sqlite3.connect(DATABASE_NAME)
    query = """
    SELECT n.*, a.nom, a.prenom
    FROM NotesDeFrais n JOIN Admins a ON n.id_user = a.id
    ORDER BY n.date_soumission DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# --- Fonctions Stock ---
def check_and_send_alert(stock_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT nom, quantite, seuil_alerte, alert_sent FROM Stock WHERE id = ?", (stock_id,))
    item = c.fetchone()
    
    if item:
        nom, quantite, seuil_alerte, alert_sent = item
        if quantite < seuil_alerte and not alert_sent:
            recipient_emails = get_admin_benevoles_emails()
            if recipient_emails:
                send_alert_email(nom, quantite, seuil_alerte, recipient_emails)
                c.execute("UPDATE Stock SET alert_sent = 1 WHERE id = ?", (stock_id,))
                conn.commit()
        elif quantite >= seuil_alerte and alert_sent:
            c.execute("UPDATE Stock SET alert_sent = 0 WHERE id = ?", (stock_id,))
            conn.commit()
            
    conn.close()

def create_stock_modification_request(user_id, stock_id, current_qty, requested_qty):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO StockModifications (id_user, id_stock, quantite_actuelle, quantite_demandee) VALUES (?, ?, ?, ?)",
              (user_id, stock_id, current_qty, requested_qty))
    conn.commit()
    conn.close()

def get_pending_stock_modifications():
    conn = sqlite3.connect(DATABASE_NAME)
    query = """
    SELECT sm.id, sm.id_stock, sm.date_demande, a.prenom, a.nom as user_nom, s.nom as stock_nom, sm.quantite_actuelle, sm.quantite_demandee
    FROM StockModifications sm
    JOIN Admins a ON sm.id_user = a.id
    JOIN Stock s ON sm.id_stock = s.id
    WHERE sm.status = 'En attente'
    ORDER BY sm.date_demande DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def approve_stock_modification(modif_id, stock_id, new_quantity):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE Stock SET quantite = ? WHERE id = ?", (new_quantity, stock_id))
    c.execute("UPDATE StockModifications SET status = 'Approuvée' WHERE id = ?", (modif_id,))
    conn.commit()
    conn.close()
    check_and_send_alert(stock_id)

def refuse_stock_modification(modif_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE StockModifications SET status = 'Refusée' WHERE id = ?", (modif_id,))
    conn.commit()
    conn.close()

def get_stock_item(stock_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM Stock WHERE id = ?", (stock_id,))
    result = c.fetchone()
    conn.close()
    return result

def add_item(nom, categorie, quantite, seuil_alerte, emoji_str):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        emoji_char = emoji_str.split(' ')[0]
        c.execute("INSERT INTO Stock (nom, categorie, quantite, seuil_alerte, emoji) VALUES (?, ?, ?, ?, ?)",
                  (nom, categorie, quantite, seuil_alerte, emoji_char))
        conn.commit()
        item_id = c.lastrowid
        check_and_send_alert(item_id)
        return True
    except sqlite3.IntegrityError:
        st.toast(f"❌ Un article avec le nom '{nom}' existe déjà.", icon='🚨')
        return False
    finally:
        conn.close()

def get_all_items():
    conn = sqlite3.connect(DATABASE_NAME)
    df = pd.read_sql_query("SELECT * FROM Stock", conn)
    conn.close()
    return df

def update_quantity(item_id, new_qty):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE Stock SET quantite = ? WHERE id = ?", (new_qty, item_id))
    conn.commit()
    conn.close()
    check_and_send_alert(item_id)

def delete_item(item_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM Stock WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def update_item_details(item_id, nom, categorie, quantite, seuil_alerte, emoji_str):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    try:
        emoji_char = emoji_str.split(' ')[0]
        c.execute("UPDATE Stock SET nom = ?, categorie = ?, quantite = ?, seuil_alerte = ?, emoji = ? WHERE id = ?",
                  (nom, categorie, quantite, seuil_alerte, emoji_char, item_id))
        conn.commit()
        check_and_send_alert(item_id)
        return True
    except sqlite3.IntegrityError:
        st.toast(f"❌ Un article avec le nom '{nom}' existe déjà. La modification a été annulée.", icon='🚨')
        return False
    finally:
        conn.close()
