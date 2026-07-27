"""SQLAlchemy ORM models — mirror of the existing MySQL schema."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DECIMAL,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ---- Stock ------------------------------------------------------------------


class Stock(Base):
    __tablename__ = "Stock"
    __table_args__ = (
        Index("idx_categorie", "categorie"),
        Index("idx_nom", "nom"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    categorie: Mapped[str] = mapped_column(String(255), nullable=False)
    sous_categorie: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantite: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seuil_alerte: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    emoji: Mapped[str | None] = mapped_column(String(10), default="📦")
    barcode: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    modifications: Mapped[list["StockModification"]] = relationship(
        "StockModification", back_populates="stock", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "Categories"
    __table_args__ = (Index("idx_cat_nom", "nom"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SubCategory(Base):
    __tablename__ = "SousCategories"
    __table_args__ = (
        UniqueConstraint("nom_categorie", "nom_sous_categorie", name="unique_category_sub"),
        Index("idx_subcat_categorie", "nom_categorie"),
        Index("idx_subcat_sous_categorie", "nom_sous_categorie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom_categorie: Mapped[str] = mapped_column(String(255), nullable=False)
    nom_sous_categorie: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---- Admins / users ---------------------------------------------------------


class Admin(Base):
    __tablename__ = "Admins"
    __table_args__ = (
        Index("idx_admins_username", "username"),
        Index("idx_admins_email", "email"),
        Index("idx_admins_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="Benevole")
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")
    nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prenom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rib: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # ``foreign_keys`` explicite : Factures et NotesDeFrais portent desormais
    # deux cles vers Admins (le deposant et le valideur), ce qui rend la
    # jointure ambigue sans desambiguisation.
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Expense.id_user",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Invoice.id_user",
    )

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.prenom, self.nom] if p]
        return " ".join(parts) if parts else self.username


class AdminInvitation(Base):
    __tablename__ = "AdminInvitations"
    __table_args__ = (
        Index("idx_inv_email", "email"),
        Index("idx_inv_token", "token_hash"),
        Index("idx_inv_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LoginAttempt(Base):
    """Compteur d'echecs de connexion, persiste en base.

    Le lockout etait auparavant un dictionnaire en memoire du process, ce qui
    posait trois problemes : il disparaissait a chaque redemarrage Passenger,
    n'etait pas partage entre workers, et grossissait sans borne puisqu'un
    echec sur un username inexistant creait une entree.

    La cle est le couple (username, ip) : verrouiller sur le seul username
    permettait a un tiers de bloquer n'importe quel compte en cinq requetes.
    """

    __tablename__ = "LoginAttempts"
    __table_args__ = (
        UniqueConstraint("username", "ip_address", name="uq_login_attempt"),
        Index("idx_login_attempt_locked_until", "locked_until"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)  # IPv6 = 45
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RefreshToken(Base):
    """Refresh tokens emis, pour permettre rotation et revocation.

    Sans cette table, ``/auth/logout`` ne pouvait rien revoquer et un refresh
    token vole restait valide sept jours. On ne stocke que le hash SHA256 du
    ``jti`` : une fuite de la base ne permet pas de rejouer les tokens.
    """

    __tablename__ = "RefreshTokens"
    __table_args__ = (
        Index("idx_refresh_user", "id_user"),
        Index("idx_refresh_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Renseigne quand le token est consomme par une rotation : si un token deja
    # tourne est represente, c'est le signe d'un vol et toute la famille saute.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---- Referentiels comptables ------------------------------------------------


class Pole(Base):
    """Pole de rattachement d'une depense (referentiel administrable).

    Calque sur ``Categories`` : le client a annonce que la liste evoluerait, donc
    une table plutot qu'une enumeration figee dans le code.
    """

    __tablename__ = "Poles"
    __table_args__ = (
        Index("idx_pole_nom", "nom"),
        Index("idx_pole_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Desactivation plutot que suppression : une facture de 2026 doit garder un
    # pole lisible meme si celui-ci n'est plus propose en 2027.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Event(Base):
    """Evenement, synchronise depuis HelloAsso ou saisi manuellement.

    La cle d'unicite porte sur ``(form_type, form_slug)`` : HelloAsso ne garantit
    l'unicite d'un slug que par type de formulaire, un ``Shop/gala`` et un
    ``Event/gala`` peuvent coexister. Les evenements saisis a la main ont un slug
    ``NULL`` — MySQL autorise les NULL multiples dans un index unique, ce qui
    permet d'en creer autant que necessaire sans contorsion.
    """

    __tablename__ = "Events"
    __table_args__ = (
        UniqueConstraint(
            "helloasso_form_type", "helloasso_form_slug", name="uq_event_helloasso"
        ),
        Index("idx_event_nom", "nom"),
        Index("idx_event_date", "date_evenement"),
        Index("idx_event_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    helloasso_form_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    helloasso_form_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    date_evenement: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    helloasso_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 'helloasso' | 'manuel' — la synchronisation ne touche jamais au manuel.
    source: Mapped[str] = mapped_column(String(20), default="helloasso", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class OutboundEmail(Base):
    """File d'attente persistante des envois au service comptable.

    Motif « transactional outbox » : l'intention d'envoyer est ecrite en base
    dans la meme transaction que la piece. Elle survit donc a un crash, a un
    redemarrage Passenger ou a une coupure SMTP — la ou un ``BackgroundTask``
    dont l'exception est avalee ne laisse aucune trace.

    ``status='sending'`` + ``locked_at`` forment un verrou : deux executions du
    cron peuvent se chevaucher, et un meme justificatif envoye deux fois au
    comptable est une vraie nuisance.
    """

    __tablename__ = "OutboundEmails"
    __table_args__ = (
        Index("idx_outmail_status", "status"),
        Index("idx_outmail_entity", "entity_type", "entity_id"),
        Index("idx_outmail_retry", "status", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipients: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # pending | sending | sent | failed | abandoned
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triggered_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---- Expenses (notes de frais) ---------------------------------------------


class Expense(Base):
    __tablename__ = "NotesDeFrais"
    __table_args__ = (
        Index("idx_nf_user", "id_user"),
        Index("idx_nf_status", "status"),
        Index("idx_nf_date_depense", "date_depense"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    date_depense: Mapped[date] = mapped_column(Date, nullable=False)
    rattachement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nature_charge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    montant: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, default=0)
    commentaires: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Montant déjà remboursé en espèces (ex: avance reçue), à soustraire du total.
    # Renommé/typé depuis `remb_emis: bool` pour aligner avec l'UI legacy qui
    # acceptait un montant. Cf. memory.md §"Pièges connus".
    remboursement_deja_emis: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), default=0, nullable=False
    )
    remise: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="En attente")
    commentaires_compta: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tracabilite comptable — cf. commentaire equivalent sur Invoice.
    validated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_soumission: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["Admin"] = relationship(
        "Admin", back_populates="expenses", foreign_keys=[id_user]
    )
    files: Mapped[list["ExpenseFile"]] = relationship(
        "ExpenseFile", back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseFile(Base):
    __tablename__ = "FichiersNotesDeFrais"
    __table_args__ = (Index("idx_fnf_note", "id_note_de_frais"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_note_de_frais: Mapped[int] = mapped_column(
        Integer, ForeignKey("NotesDeFrais.id", ondelete="CASCADE"), nullable=False
    )
    nom_fichier: Mapped[str] = mapped_column(String(255), nullable=False)
    chemin_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    taille_fichier: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type_fichier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_upload: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    expense: Mapped["Expense"] = relationship("Expense", back_populates="files")


# ---- Invoices ---------------------------------------------------------------


class Invoice(Base):
    __tablename__ = "Factures"
    __table_args__ = (
        Index("idx_facture_user", "id_user"),
        Index("idx_facture_status", "status"),
        Index("idx_facture_date_depot", "date_depot"),
        Index("idx_facture_pole", "id_pole"),
        Index("idx_facture_event", "id_event"),
        Index("idx_facture_date_evenement", "date_evenement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_depot: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="En attente")

    # ---- Rattachement comptable -------------------------------------------
    # Chaque champ existe en double : l'identifiant pour filtrer et agreger, le
    # libelle en clair comme instantane. Le nom du PDF envoye au comptable est
    # fige au depot ; renommer un pole six mois plus tard ne doit pas desaligner
    # les fichiers deja dans sa boite mail. Meme raisonnement que
    # BuvetteSale.product_name_snapshot.
    # Le champ texte de l'evenement porte aussi le cas « saisie libre », quand
    # l'evenement n'existe pas cote HelloAsso (facture d'electricite, achat
    # courant) : id_event vaut alors NULL.
    # Tout est nullable : la table contient des lignes en production, et
    # l'obligation de saisie est portee par Pydantic pour les nouveaux depots.
    id_pole: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pole: Mapped[str | None] = mapped_column(String(120), nullable=True)
    id_event: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evenement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_evenement: Mapped[date | None] = mapped_column(Date, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    montant: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)

    # Tracabilite comptable : sans ces deux colonnes, il etait impossible de
    # savoir quel comptable avait valide quelle facture, ni quand.
    validated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["Admin"] = relationship(
        "Admin", back_populates="invoices", foreign_keys=[id_user]
    )
    files: Mapped[list["InvoiceFile"]] = relationship(
        "InvoiceFile", back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceFile(Base):
    __tablename__ = "FichiersFactures"
    __table_args__ = (Index("idx_ff_facture", "id_facture"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_facture: Mapped[int] = mapped_column(
        Integer, ForeignKey("Factures.id", ondelete="CASCADE"), nullable=False
    )
    nom_fichier: Mapped[str] = mapped_column(String(255), nullable=False)
    chemin_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    taille_fichier: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type_fichier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_upload: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="files")


# ---- Stock modifications ----------------------------------------------------


class StockModification(Base):
    __tablename__ = "StockModifications"
    __table_args__ = (
        Index("idx_sm_user", "id_user"),
        Index("idx_sm_stock", "id_stock"),
        Index("idx_sm_status", "status"),
        Index("idx_sm_date_demande", "date_demande"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    id_stock: Mapped[int] = mapped_column(
        Integer, ForeignKey("Stock.id", ondelete="CASCADE"), nullable=False
    )
    quantite_actuelle: Mapped[int] = mapped_column(Integer, nullable=False)
    quantite_demandee: Mapped[int] = mapped_column(Integer, nullable=False)
    date_demande: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="En attente")
    approuve_par: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="SET NULL"), nullable=True
    )
    date_approbation: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    commentaires: Mapped[str | None] = mapped_column(Text, nullable=True)

    stock: Mapped["Stock"] = relationship("Stock", back_populates="modifications")
    user: Mapped["Admin"] = relationship("Admin", foreign_keys=[id_user])
    approver: Mapped["Admin | None"] = relationship("Admin", foreign_keys=[approuve_par])


# ---- Buvette (HelloAsso) ----------------------------------------------------


class BuvetteProduct(Base):
    __tablename__ = "BuvetteProducts"
    __table_args__ = (
        Index("idx_buvette_prod_tier", "helloasso_tier_id"),
        Index("idx_buvette_prod_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    helloasso_tier_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seuil_alerte: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    emoji: Mapped[str | None] = mapped_column(String(10), default="🥤")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    barcode: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        server_default=func.now(),
    )

    sales: Mapped[list["BuvetteSale"]] = relationship(
        "BuvetteSale", back_populates="product"
    )

    @property
    def low_stock(self) -> bool:
        return self.quantity < self.seuil_alerte


class BuvetteSale(Base):
    __tablename__ = "BuvetteSales"
    __table_args__ = (
        UniqueConstraint(
            "helloasso_payment_id", "helloasso_item_id", name="uq_sale_payment_item"
        ),
        Index("idx_buvette_sale_order", "helloasso_order_id"),
        Index("idx_buvette_sale_payment", "helloasso_payment_id"),
        Index("idx_buvette_sale_item", "helloasso_item_id"),
        Index("idx_buvette_sale_product", "buvette_product_id"),
        Index("idx_buvette_sale_processed", "processed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    helloasso_order_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    helloasso_payment_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    helloasso_item_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    buvette_product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("BuvetteProducts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customer_first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_event: Mapped[str | None] = mapped_column(Text, nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, server_default=func.now()
    )

    product: Mapped["BuvetteProduct | None"] = relationship(
        "BuvetteProduct", back_populates="sales"
    )


__all__ = [
    "Stock",
    "Category",
    "SubCategory",
    "Admin",
    "AdminInvitation",
    "Expense",
    "ExpenseFile",
    "Invoice",
    "InvoiceFile",
    "StockModification",
    "BuvetteProduct",
    "BuvetteSale",
]
