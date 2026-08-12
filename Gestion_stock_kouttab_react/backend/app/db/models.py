"""SQLAlchemy ORM models — mirror of the existing MySQL schema."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    LargeBinary,
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
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import ChampChiffre


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
    # Chiffre au repos : c'est le champ le plus sensible de la base, et les
    # permissions applicatives ne protegent rien de ce qui contourne
    # l'application (export, sauvegarde, acces MySQL direct).
    rib: Mapped[str | None] = mapped_column(ChampChiffre(255), nullable=True)
    # Releve d'identite bancaire depose par le benevole : le document de sa
    # banque, que la comptabilite telecharge au moment de payer. L'IBAN saisi
    # ci-dessus sert au virement, ce document sert de preuve.
    #
    # En base comme les justificatifs, et `deferred` pour la meme raison :
    # lister les utilisateurs ne doit pas rapatrier les pieces de chacun.
    #
    # Le contenu n'est pas chiffre, contrairement a `rib` : un BLOB traverserait
    # mal `ChampChiffre`, concu pour du texte, et la protection utile ici est le
    # controle d'acces — proprietaire, Compta, Super Admin.
    rib_document: Mapped[bytes | None] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True, deferred=True
    )
    rib_document_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rib_document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
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


class PasswordReset(Base):
    """Jeton de reinitialisation de mot de passe.

    Meme patron que ``AdminInvitation`` : seul le SHA256 du jeton est stocke, si
    bien qu'une fuite de la base ne permet pas de fabriquer un lien valide.

    Table distincte plutot que reutilisation des invitations : une invitation
    *cree* un compte, une reinitialisation en *modifie* un existant. Les
    confondre reviendrait a laisser un lien d'invitation changer le mot de passe
    d'un compte deja en place.

    ``id_user`` et non l'adresse : elle peut changer entre la demande et le
    clic, et le jeton doit rester rattache au compte, pas a une chaine.
    """

    __tablename__ = "PasswordResets"
    __table_args__ = (
        Index("idx_reset_token", "token_hash"),
        Index("idx_reset_user", "id_user"),
        Index("idx_reset_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requested_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
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
    # Ce que le depot demande sous ce pole : un evenement, ou une categorie.
    #
    # Seul le pole evenementiel se rattache a un evenement. Une depense du local
    # — des courses, du gouter, du materiel — n'en a aucun, et l'exiger obligeait
    # a inventer un libelle pour satisfaire le formulaire. Le drapeau vit sur le
    # pole plutot que dans le code : un pole cree demain declare lui-meme ce
    # qu'il attend, sans redeploiement.
    requiert_evenement: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Famille d'evenements proposee sous ce pole : « T », « G », « J »...
    #
    # Les poles evenementiels sont declines par famille (EV(T), EV(G), EV(J)) et
    # n'ont pas a proposer les evenements des autres. `NULL` = aucun filtre, la
    # liste complete est proposee.
    type_evenement: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExpenseCategory(Base):
    """Categorie d'une depense hors evenement (referentiel administrable).

    Ce que l'evenement est au pole evenementiel, la categorie l'est aux autres :
    la deuxieme composante du nom du justificatif envoye au comptable, celle qui
    dit a quoi la depense se rattache. « Local_Courses_2026-08-12.pdf » s'impute
    sans avoir a ouvrir le PDF.

    Table plutot qu'enumeration figee, comme ``Poles`` et pour la meme raison :
    la liste evoluera, et la faire evoluer ne doit pas demander un deploiement.
    """

    __tablename__ = "CategoriesDepense"
    __table_args__ = (
        Index("idx_catdep_nom", "nom"),
        Index("idx_catdep_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Desactivation plutot que suppression, meme raison que pour les poles : une
    # note de 2026 doit rester lisible si la categorie disparait en 2027.
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
    # Famille de l'evenement : « T », « G », « J ». Elle determine sous quel
    # pole EV il apparait au depot.
    #
    # Renseignee a la main : HelloAsso ne connait pas cette classification, et la
    # synchronisation n'y touche donc jamais. Un evenement non classe (`NULL`)
    # reste propose sous TOUS les poles EV — sans quoi la premiere
    # synchronisation viderait les listes, chaque evenement importe arrivant
    # sans famille.
    type_ev: Mapped[str | None] = mapped_column(String(10), nullable=True)
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


# ---- Tickets de justificatif ------------------------------------------------


class JustificatifTicket(Base):
    """Demande de justificatif adressee a un benevole.

    La comptabilite sait qu'un achat a eu lieu — elle voit le debit, ou on le lui
    a dit — mais n'a pas la facture. Elle relancait de memoire, par messages
    prives, sans trace : impossible de savoir qui avait deja ete relance, ni
    combien de pieces manquaient encore a la cloture.

    Un ticket porte cette demande, ses relances, et sa fin. Seul ``libelle`` est
    obligatoire : ouvrir un ticket doit rester possible avec ce qu'on a sous la
    main, quitte a completer plus tard.

    La cloture est **manuelle**. Fermer sur le premier depot du benevole aurait
    ferme le ticket a tort des qu'il depose une facture sans rapport, et les
    relances se seraient tues alors que la piece attendue manquait toujours.
    """

    __tablename__ = "TicketsJustificatif"
    __table_args__ = (
        Index("idx_ticket_user", "id_user"),
        Index("idx_ticket_statut", "statut"),
    )

    STATUT_OUVERT = "ouvert"
    STATUT_CLOS = "clos"
    STATUT_ANNULE = "annule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Le benevole a qui la piece est demandee.
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    cree_par: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="SET NULL"), nullable=True
    )

    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tout ce qui suit est facultatif : la comptabilite ouvre un ticket avec ce
    # qu'elle sait, et le courriel de relance ne mentionne que ce qui est rempli.
    montant_attendu: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    date_achat: Mapped[date | None] = mapped_column(Date, nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String(255), nullable=True)

    statut: Mapped[str] = mapped_column(String(20), default=STATUT_OUVERT, nullable=False)
    # Piece qui solde le ticket, rattachee a la main par la comptabilite.
    id_facture: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Factures.id", ondelete="SET NULL"), nullable=True
    )

    rappels_envoyes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dernier_rappel_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["Admin"] = relationship("Admin", foreign_keys=[id_user])
    facture: Mapped["Invoice | None"] = relationship("Invoice", foreign_keys=[id_facture])


# ---- Remboursements ---------------------------------------------------------


class Reimbursement(Base):
    """Un versement a un benevole, soldant une ou plusieurs notes de frais.

    La comptabilite ne rembourse pas note par note : elle vire un montant a une
    personne, couvrant toutes ses depenses approuvees. Cette table represente ce
    versement, et le justificatif remis a la comptabilite (PDF + tableur) en
    decoule directement.

    ``montant_total`` est un INSTANTANE, comme ``Invoice.pole`` ou
    ``BuvetteSale.product_name_snapshot`` : il fige ce qui a reellement ete vire.
    Recalculer ce total a partir des notes ferait bouger un chiffre deja
    justifie le jour ou l'une d'elles serait corrigee.
    """

    __tablename__ = "Remboursements"
    __table_args__ = (
        Index("idx_remb_user", "id_user"),
        Index("idx_remb_date", "date_remboursement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_user: Mapped[int] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="CASCADE"), nullable=False
    )
    date_remboursement: Mapped[date] = mapped_column(Date, nullable=False)

    # Bloc « Apurement » du modele remis a la comptabilite. Listes figees cote
    # application (cf. `core/reimbursement_options.py`), stockees en clair : le
    # justificatif deja emis doit rester lisible si ces listes evoluent.
    moyen: Mapped[str] = mapped_column(String(50), nullable=False)
    etablissement: Mapped[str] = mapped_column(String(80), nullable=False)
    approuve_par: Mapped[str] = mapped_column(String(120), nullable=False)

    montant_total: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Documents produits au moment du remboursement. Ils vivent dans OUTBOX_DIR,
    # hors de `uploads/` : leurs noms sont previsibles.
    chemin_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chemin_xlsx: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cree_par: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Admins.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["Admin"] = relationship("Admin", foreign_keys=[id_user])
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="reimbursement", foreign_keys="Expense.id_remboursement"
    )


# ---- Expenses (notes de frais) ---------------------------------------------


class Expense(Base):
    __tablename__ = "NotesDeFrais"
    __table_args__ = (
        Index("idx_nf_user", "id_user"),
        Index("idx_nf_status", "status"),
        Index("idx_nf_date_depense", "date_depense"),
        Index("idx_nf_pole", "id_pole"),
        Index("idx_nf_event", "id_event"),
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

    # Remboursement qui a solde cette note. NULL tant qu'elle n'est pas payee.
    #
    # La comptabilite rembourse un BENEVOLE, pas une note : un virement couvre
    # plusieurs depenses. Ce rattachement permet de retrouver, depuis n'importe
    # quelle note, le versement qui l'a soldee et le justificatif remis.
    id_remboursement: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("Remboursements.id", ondelete="SET NULL"), nullable=True
    )

    # ---- Rattachement comptable -------------------------------------------
    # Memes champs que Factures, pour que le comptable recoive les tickets de
    # caisse et les factures sous une nomenclature identique. Identifiant +
    # libelle en double, meme raisonnement que sur Invoice : le nom du PDF est
    # fige au depot. `rattachement` est conserve tel quel, il precede ces champs
    # et reste renseigne sur les notes existantes.
    id_pole: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pole: Mapped[str | None] = mapped_column(String(120), nullable=True)
    id_event: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evenement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_evenement: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Alternative a l'evenement, sous un pole qui n'en attend pas (cf. Invoice).
    id_categorie: Mapped[int | None] = mapped_column(Integer, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String(120), nullable=True)

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
    reimbursement: Mapped["Reimbursement | None"] = relationship(
        "Reimbursement", back_populates="expenses", foreign_keys=[id_remboursement]
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
    # Contenu binaire du justificatif, stocke EN BASE.
    #
    # Les fichiers vivaient uniquement sur le disque du VPS, hors de toute
    # sauvegarde : la table ne gardait qu'un chemin, et perdre la machine
    # revenait a perdre des pieces comptables a conserver plusieurs annees.
    # Mesure faite : 11 Mo pour l'ensemble des justificatifs, le plus gros
    # fichier a 4,5 Mo. A cette echelle, la base — deja sauvegardee par
    # O2Switch — est le bon endroit, et supprime le probleme au lieu d'ajouter
    # un mecanisme de sauvegarde de plus.
    #
    # `deferred=True` est INDISPENSABLE : sans lui, lister les notes de frais
    # chargerait tous les octets de tous les justificatifs en memoire, depuis
    # une base distante. Le contenu n'est lu qu'a l'acces explicite.
    #
    # `chemin_fichier` est conserve : il reste renseigne, sert de repli pour
    # les pieces anterieures a la migration, et documente d'ou vient le fichier.
    contenu: Mapped[bytes | None] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"),
        nullable=True,
        deferred=True,
    )
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
    # Alternative a l'evenement, sous un pole qui n'en attend pas. Identifiant
    # et libelle en double, meme raison que pour le pole : le nom du PDF deja
    # envoye ne doit pas bouger si la categorie est renommee.
    id_categorie: Mapped[int | None] = mapped_column(Integer, nullable=True)
    categorie: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
    # Contenu binaire du justificatif, stocke EN BASE.
    #
    # Les fichiers vivaient uniquement sur le disque du VPS, hors de toute
    # sauvegarde : la table ne gardait qu'un chemin, et perdre la machine
    # revenait a perdre des pieces comptables a conserver plusieurs annees.
    # Mesure faite : 11 Mo pour l'ensemble des justificatifs, le plus gros
    # fichier a 4,5 Mo. A cette echelle, la base — deja sauvegardee par
    # O2Switch — est le bon endroit, et supprime le probleme au lieu d'ajouter
    # un mecanisme de sauvegarde de plus.
    #
    # `deferred=True` est INDISPENSABLE : sans lui, lister les notes de frais
    # chargerait tous les octets de tous les justificatifs en memoire, depuis
    # une base distante. Le contenu n'est lu qu'a l'acces explicite.
    #
    # `chemin_fichier` est conserve : il reste renseigne, sert de repli pour
    # les pieces anterieures a la migration, et documente d'ou vient le fichier.
    contenu: Mapped[bytes | None] = mapped_column(
        LargeBinary().with_variant(LONGBLOB(), "mysql"),
        nullable=True,
        deferred=True,
    )
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
