import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import (get_stock_statistics, get_stock_modifications_history, 
                      get_recent_stock_changes, get_low_stock_items, 
                      get_all_items, approve_stock_modification, 
                      refuse_stock_modification, get_admin_benevoles_emails)
from email_utils import send_alert_email
from logger_config import logger

def display_dashboard_page(user_id, user_role):
    st.header("📊 Tableau de Bord - États des Stocks")
    
    # Onglets principaux
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Vue d'ensemble", "📝 Historique", "⚠️ Alertes", "🔄 Modifications"])
    
    with tab1:
        display_overview()
    
    with tab2:
        display_history()
    
    with tab3:
        display_alerts()
    
    with tab4:
        display_modifications_management()

def display_overview():
    st.subheader("📈 Vue d'ensemble du stock")
    
    # Récupérer les statistiques
    stats = get_stock_statistics()
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 Total Articles", stats['total_articles'], delta=None)
    with col2:
        st.metric("📊 Total Quantité", stats['total_quantite'], delta=None)
    with col3:
        st.metric("⚠️ Articles en alerte", stats['alertes_stock'], delta=None)
    with col4:
        st.metric("📦 Stock épuisé", stats['stock_epuise'], delta=None)
    
    st.markdown("---")
    
    # Graphique des catégories
    if stats['stats_par_categorie']:
        st.subheader("📊 Répartition par catégorie")

        cat_data = pd.DataFrame(stats['stats_par_categorie'],
                              columns=['categorie', 'count', 'total'])

        # Créer un graphique en barres
        st.bar_chart(cat_data.set_index('categorie')['count'])

        # Titre séparé
        st.write("**Nombre d'articles par catégorie**")

        # Tableau détaillé
        st.write("**Détail par catégorie :**")
        cat_data_display = cat_data.rename(columns={
            'categorie': 'Catégorie',
            'count': 'Nombre d\'articles',
            'total': 'Quantité totale'
        })
        st.dataframe(cat_data_display, width='stretch')

    # Dernières activités
    if stats['dernieres_modifs']:
        st.subheader("🕐 Dernières activités")
        for mod in stats['dernieres_modifs'][:5]:
            date_mod = datetime.strptime(mod[0], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            user_name = f"{mod[1]} {mod[2]}"
            
            status_color = {
                'En attente': '🟡',
                'Approuvée': '🟢', 
                'Refusée': '🔴'
            }
            
            status_emoji = status_color.get(mod[5], '⚪')
            
            st.write(f"{status_emoji} **{date_mod}** - {user_name} a {mod[5].lower()} {mod[6]} unité(s) pour **{mod[3]}** ({mod[4]})")

def display_history():
    st.subheader("📝 Historique complet des modifications")
    
    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        days_filter = st.selectbox("Période", 
                                options=[1, 7, 30, 90], 
                                index=1,
                                format_func=lambda x: f"Derniers {x} jour(s)")
    with col2:
        status_filter = st.selectbox("Statut", 
                                  options=["Tous", "En attente", "Approuvée", "Refusée"],
                                  index=0)
    
    # Récupérer l'historique
    history_df = get_stock_modifications_history()
    
    # Appliquer les filtres
    if status_filter != "Tous":
        history_df = history_df[history_df['status'] == status_filter]
    
    # Filtrer par date si nécessaire
    if days_filter != 90:
        cutoff_date = datetime.now() - timedelta(days=days_filter)
        history_df['date_demande'] = pd.to_datetime(history_df['date_demande'])
        history_df = history_df[history_df['date_demande'] >= cutoff_date]
    
    if history_df.empty:
        st.info("Aucune modification trouvée pour cette période.")
        return
    
    # Afficher l'historique
    st.write(f"**{len(history_df)} modification(s) trouvée(s)**")
    
    # Statistiques de l'historique
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("En attente", len(history_df[history_df['status'] == 'En attente']))
    with col2:
        st.metric("Approuvées", len(history_df[history_df['status'] == 'Approuvée']))
    with col3:
        st.metric("Refusées", len(history_df[history_df['status'] == 'Refusée']))
    
    # Tableau détaillé
    history_display = history_df[[
        'date_demande', 'nom', 'prenom', 'stock_nom', 'categorie', 
        'sous_categorie', 'quantite_actuelle', 'quantite_demandee', 'status'
    ]].rename(columns={
        'date_demande': 'Date',
        'nom': 'Nom utilisateur',
        'prenom': 'Prénom',
        'stock_nom': 'Article',
        'categorie': 'Catégorie',
        'sous_categorie': 'Sous-catégorie',
        'quantite_actuelle': 'Quantité actuelle',
        'quantite_demandee': 'Quantité demandée',
        'status': 'Statut'
    })
    
    st.dataframe(history_display, width='stretch')

def display_alerts():
    st.subheader("⚠️ Articles en alerte de stock")
    
    # Récupérer les articles en alerte
    low_stock_df = get_low_stock_items()
    
    if low_stock_df.empty:
        st.success("✅ Aucun article en alerte de stock !")
        return
    
    st.warning(f"🚨 {len(low_stock_df)} article(s) nécessite(nt) une attention !")
    
    # Statistiques des alertes
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Articles critiques", 
                  len(low_stock_df[low_stock_df['quantite'] == 0]))
    with col2:
        st.metric("Articles bas", 
                  len(low_stock_df[low_stock_df['quantite'] > 0]))
    
    # Tableau des alertes
    alert_display = low_stock_df[[
        'nom', 'categorie', 'sous_categorie', 'quantite', 'seuil_alerte', 'emoji'
    ]].copy()
    
    # Renommer les colonnes
    alert_display.columns = ['Article', 'Catégorie', 'Sous-catégorie', 'Quantité actuelle', 'Seuil d\'alerte', 'Emoji']
    
    # Ajouter une colonne de criticité
    alert_display['Criticité'] = alert_display['Quantité actuelle'].apply(
        lambda x: '🔴 Critique' if x == 0 else '🟡 Bas'
    )
    
    st.dataframe(alert_display, width='stretch')
    
    # Actions rapides
    st.markdown("---")
    st.subheader("🚀 Actions rapides")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📧 Envoyer un email d'alerte", type="primary"):
            # Récupérer les articles en alerte
            low_stock_items = get_low_stock_items()
            
            if not low_stock_items.empty:
                # Récupérer les emails des admins bénévoles
                recipient_emails = get_admin_benevoles_emails()
                
                if recipient_emails:
                    # Créer le contenu de l'email récapitulatif
                    items_list = []
                    for _, item in low_stock_items.iterrows():
                        status = "🔴 ÉPUISÉ" if item['quantite'] == 0 else "🟡 BAS"
                        items_list.append(f"- {item['nom']} : {item['quantite']} (seuil: {item['seuil_alerte']}) {status}")
                    
                    # Envoyer un email récapitulatif personnalisé
                    try:
                        import smtplib
                        from email.mime.text import MIMEText
                        from email.mime.multipart import MIMEMultipart
                        
                        # Récupérer les identifiants depuis les secrets
                        sender_email = st.secrets["email_credentials"]["sender_email"]
                        sender_password = st.secrets["email_credentials"]["sender_password"]
                        
                        # Création du message récapitulatif
                        subject = f"🚨 Alerte Stock - {len(low_stock_items)} article(s) nécessite(nt) une attention"
                        body = f"""
Bonjour,

Ceci est une alerte automatique de l'application de gestion de stock.

Les articles suivants ont atteint un niveau de stock critique :

{chr(10).join(items_list)}

Veuillez s'il vous plaît prévoir un réapprovisionnement dès que possible.

Total : {len(low_stock_items)} article(s) en alerte
- {len(low_stock_items[low_stock_items['quantite'] == 0])} article(s) épuisé(s)
- {len(low_stock_items[low_stock_items['quantite'] > 0])} article(s) avec stock bas

Cordialement,
Votre système de Gestion de Stock Le Kouttâb
                        """
                        
                        message = MIMEMultipart()
                        message["From"] = sender_email
                        message["To"] = ", ".join(recipient_emails)
                        message["Subject"] = subject
                        message.attach(MIMEText(body, "plain"))
                        
                        # Envoi de l'e-mail
                        server = smtplib.SMTP("smtp.gmail.com", 587)
                        server.starttls()
                        server.login(sender_email, sender_password)
                        server.sendmail(sender_email, recipient_emails, message.as_string())
                        server.quit()
                        
                        st.success(f"📧 Email récapitulatif envoyé à {len(recipient_emails)} responsable(s) pour {len(low_stock_items)} article(s) !")
                        logger.info(f"Email récapitulatif de stock envoyé pour {len(low_stock_items)} articles")
                        
                    except Exception as e:
                        st.error(f"❌ Erreur lors de l'envoi de l'email : {e}")
                        logger.error(f"Erreur envoi email récapitulatif : {e}")
                else:
                    st.warning("⚠️ Aucun email d'admin bénévole trouvé pour l'envoi d'alerte.")
            else:
                st.info("✅ Aucun article en alerte, aucun email envoyé.")
    
    with col2:
        if st.button("📊 Générer un rapport PDF"):
            st.info("Fonctionnalité de génération PDF à venir...")

def display_modifications_management():
    st.subheader("🔄 Gestion des modifications en attente")
    
    # Récupérer les changements récents
    recent_changes = get_recent_stock_changes(days=30)
    
    if not recent_changes:
        st.info("Aucune modification récente à valider.")
        return
    
    # Filtrer les modifications en attente
    pending_changes = [change for change in recent_changes if change[7] == 'En attente']
    
    if not pending_changes:
        st.success("✅ Toutes les modifications récentes ont été traitées !")
        return
    
    st.warning(f"📋 {len(pending_changes)} modification(s) en attente de validation")
    
    # Afficher les modifications en attente (lecture seule)
    for i, change in enumerate(pending_changes):
        with st.expander(f"🔄 Modification #{i+1} - {change[0]} ({change[3]})"):
            st.write(f"**Article :** {change[0]}")
            st.write(f"**Catégorie :** {change[1]}")
            if change[2]:  # sous-catégorie peut être None
                st.write(f"**Sous-catégorie :** {change[2]}")
            st.write(f"**Quantité actuelle :** {change[3]}")
            st.write(f"**Quantité demandée :** {change[4]}")
            st.write(f"**Demandé par :** {change[8]} {change[9]}")
            st.write(f"**Date :** {change[5]}")
            st.info("👁️ Pour approuver ou refuser cette modification, allez dans l'onglet **Administration**")
    
    # Statistiques des modifications
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total 30 jours", len(recent_changes))
    with col2:
        st.metric("En attente", len(pending_changes))
    with col3:
        approved_count = len([c for c in recent_changes if c[7] == 'Approuvée'])
        st.metric("Approuvées", approved_count)
