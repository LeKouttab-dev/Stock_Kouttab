"""Buvette / HelloAsso schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


# Onglets de la tablette de caisse. Liste figee : chaque valeur correspond a un
# onglet code dans l'application Android, une valeur inconnue n'y serait
# affichee nulle part.
CaisseCategory = Literal["sucre_sale", "boissons", "cafe", "epicerie"]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class BuvetteProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(ge=0, default=0)
    quantity: int = Field(ge=0, default=0)
    seuil_alerte: int = Field(ge=0, default=5)
    emoji: str | None = "🥤"
    barcode: str | None = Field(default=None, max_length=32)


class BuvetteProductCreate(BaseModel):
    """Manual creation of a buvette product (not synced from HelloAsso)."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(ge=0, default=0)
    quantity: int = Field(ge=0, default=0)
    seuil_alerte: int = Field(ge=0, default=5)
    emoji: str | None = "🥤"
    image_url: str | None = None
    barcode: str | None = Field(default=None, max_length=32)
    helloasso_tier_id: int | None = None
    is_active: bool = True
    caisse_category: CaisseCategory | None = None


class BuvetteProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=0)
    seuil_alerte: int | None = Field(default=None, ge=0)
    emoji: str | None = None
    image_url: str | None = None
    barcode: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    # `null` explicite = retirer le produit de la tablette ; absent = inchange.
    caisse_category: CaisseCategory | None = None


class BuvetteProductOut(BaseModel):
    id: int
    helloasso_tier_id: int | None = None
    name: str
    description: str | None = None
    price_cents: int
    quantity: int
    seuil_alerte: int
    emoji: str | None = "🥤"
    image_url: str | None = None
    barcode: str | None = None
    is_active: bool = True
    caisse_category: CaisseCategory | None = None
    # Vrai des qu'un champ ecrit aussi par HelloAsso a ete modifie a la main
    # (nom, description, prix, photo). L'ecran l'affiche : sans cela, personne
    # ne peut savoir pourquoi « Synchroniser » ne change plus ce produit.
    edite_manuellement: bool = False
    # Present quand une photo a ete deposee : l'ecran propose alors de la
    # remplacer ou de la retirer, plutot que seulement d'en ajouter une.
    a_une_photo: bool = False
    alert_sent: bool = False
    last_synced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def low_stock(self) -> bool:
        return self.quantity < self.seuil_alerte


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


class BuvetteSaleOut(BaseModel):
    id: int
    source: Literal["helloasso", "caisse"] = "helloasso"
    caisse_tx_id: str | None = None
    sumup_tx_code: str | None = None
    helloasso_order_id: int | None = None
    helloasso_payment_id: int | None = None
    helloasso_item_id: int | None = None
    buvette_product_id: int | None = None
    product_name_snapshot: str
    quantity_sold: int
    amount_cents: int
    customer_first_name: str | None = None
    customer_last_name: str | None = None
    customer_email: str | None = None
    sold_at: datetime | None = None
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Caisse (tablette SumUp)
# ---------------------------------------------------------------------------


class CaisseProduitOut(BaseModel):
    """Ce que la tablette affiche d'un produit, et rien de plus."""

    id: int
    name: str
    price_cents: int
    category: CaisseCategory
    emoji: str | None = None
    # Photo de l'article (celle de la boutique HelloAsso). La tablette la garde
    # en cache et reprend l'emoji quand elle manque ou ne se charge pas.
    image_url: str | None = None
    quantity: int
    low_stock: bool


class CaisseCatalogueOut(BaseModel):
    products: list[CaisseProduitOut]
    generated_at: datetime


class CaisseVersionOut(BaseModel):
    """Ce que la tablette lit pour decider si elle doit se mettre a jour.

    Elle n'agit que si `version_code` **depasse** celui qu'elle execute, et
    verifie `sha256` avant d'installer : une empreinte qui ne correspond pas
    fait supprimer le telechargement sans rien installer.
    """

    version_code: int
    version_name: str
    sha256: str


class CaisseVersionAdminOut(CaisseVersionOut):
    """La meme chose pour l'ecran d'administration, avec de quoi se reperer."""

    taille: int
    depose_le: str


class CaisseLigneIn(BaseModel):
    """Une ligne du panier encaisse.

    `product_id` peut viser un produit supprime depuis le dernier catalogue : la
    vente est gardee sans decrement plutot que perdue. Le nom sert d'instantane.
    """

    product_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=1, le=100)
    unit_price_cents: int = Field(ge=0, le=100_000)


class CaisseVenteIn(BaseModel):
    # Le `foreignTransactionId` transmis a SumUp : l'identifiant qui rend la
    # vente idempotente. Alphabet restreint, il finit dans les journaux.
    transaction_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    sumup_tx_code: str | None = Field(default=None, max_length=64)
    total_cents: int = Field(ge=0)
    sold_at: datetime | None = None
    # La coherence total / detail est controlee dans `crud.record_caisse_sale`,
    # et non par un `model_validator` : le gestionnaire des erreurs de
    # validation ne sait pas serialiser l'exception qu'il porterait (500).
    lines: list[CaisseLigneIn] = Field(min_length=1, max_length=50)


class CaisseVenteOut(BaseModel):
    transaction_id: str
    status: Literal["recorded", "already_recorded"]
    lines: int


# ---------------------------------------------------------------------------
# Etat de la tablette (heartbeat)
# ---------------------------------------------------------------------------


def _tronquer_32(valeur: Any) -> Any:
    # Tronque plutot que refuser : un releve rejete pour un nom d'ecran trop
    # long ferait passer une tablette en parfait etat pour muette.
    return valeur[:32] if isinstance(valeur, str) else valeur


class CaisseEtatIn(BaseModel):
    """Ce que la tablette envoie toutes les minutes (`POST /buvette/caisse/etat`)."""

    batterie_pct: int | None = None
    en_charge: bool | None = None
    version_code: int = Field(ge=0)
    version_name: str = Field(max_length=200)
    sumup_connecte: bool
    lecteur_connecte: bool
    lecteur_batterie_pct: int | None = None
    ventes_en_attente: int = Field(ge=0)
    ventes_rejetees: int = Field(ge=0)
    # "accueil" | "buvette" | "especes" | "merci" | "personnel" ; texte libre.
    ecran: str = Field(max_length=200)

    @field_validator("version_name", "ecran", mode="after")
    @classmethod
    def _court(cls, valeur: str) -> str:
        return _tronquer_32(valeur)


class CaisseEtatOut(BaseModel):
    batterie_pct: int | None = None
    en_charge: bool | None = None
    version_code: int
    version_name: str
    sumup_connecte: bool
    lecteur_connecte: bool
    lecteur_batterie_pct: int | None = None
    ventes_en_attente: int
    ventes_rejetees: int
    ecran: str
    recu_at: datetime
    secondes_depuis: int


class CaisseEtatEnveloppeOut(BaseModel):
    """`etat` vaut `null` tant que la tablette n'a jamais rien envoye."""

    etat: CaisseEtatOut | None = None


# ---------------------------------------------------------------------------
# Reapprovisionnement (increment atomique)
# ---------------------------------------------------------------------------


class ReapproIn(BaseModel):
    # Borne haute : un +5000 par faute de frappe fausserait le stock pour des
    # semaines. Les boutons de l'ecran vont de +5 a +30.
    delta: int = Field(ge=1, le=500)


class CaisseReapproIn(ReapproIn):
    product_id: int


class CaisseReapproOut(BaseModel):
    id: int
    name: str
    quantity: int


# ---------------------------------------------------------------------------
# Suivi des paiements
# ---------------------------------------------------------------------------


MoyenDePaiement = Literal["carte", "especes", "helloasso"]


class PaiementArticleOut(BaseModel):
    nom: str
    quantite: int
    montant_cents: int


class PaiementOut(BaseModel):
    cle: str
    moyen: MoyenDePaiement
    sold_at: datetime
    total_cents: int
    sumup_tx_code: str | None = None
    helloasso_order_id: int | None = None
    client: str | None = None
    articles: list[PaiementArticleOut]


class PaiementsTotauxOut(BaseModel):
    carte_cents: int = 0
    especes_cents: int = 0
    helloasso_cents: int = 0
    total_cents: int = 0
    nb_ventes: int = 0


class PaiementsOut(BaseModel):
    paiements: list[PaiementOut]
    totaux: PaiementsTotauxOut


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------


class StatJourOut(BaseModel):
    jour: date
    ca_cents: int
    ventes: int


class StatHeureOut(BaseModel):
    heure: int
    ca_cents: int
    ventes: int


class StatProduitOut(BaseModel):
    nom: str
    quantite: int
    ca_cents: int


class StatMoyenOut(BaseModel):
    moyen: MoyenDePaiement
    ca_cents: int
    ventes: int


class StatsOut(BaseModel):
    par_jour: list[StatJourOut]
    par_heure: list[StatHeureOut]
    par_produit: list[StatProduitOut]
    par_moyen: list[StatMoyenOut]


# ---------------------------------------------------------------------------
# Cloture de caisse especes
# ---------------------------------------------------------------------------


class ClotureIn(BaseModel):
    jour: date
    compte_cents: int = Field(ge=0, le=10_000_000)
    commentaire: str | None = Field(default=None, max_length=2000)


class ClotureOut(BaseModel):
    id: int
    jour: date
    attendu_cents: int
    compte_cents: int
    # compte - attendu : negatif = il manque de l'argent dans la caisse.
    ecart_cents: int
    commentaire: str | None = None
    saisi_par: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClotureAttenduOut(BaseModel):
    jour: date
    attendu_cents: int
    nb_ventes_especes: int
    cloture: ClotureOut | None = None


# ---------------------------------------------------------------------------
# Reglages
# ---------------------------------------------------------------------------


class CompteAdminStockOut(BaseModel):
    id: int
    email: str
    nom: str


class ReglagesOut(BaseModel):
    recap_destinataires: list[str]
    # Lecture seule : les comptes actifs du role « AdminStock », qui recoivent
    # aussi les courriels de la buvette.
    comptes_admin_stock: list[CompteAdminStockOut]


class ReglagesIn(BaseModel):
    # Adresses validees dans `crud.buvette.enregistrer_destinataires` et non par
    # un validateur pydantic : le gestionnaire des erreurs de validation ne sait
    # pas serialiser l'exception qu'un validateur porterait (500).
    recap_destinataires: list[str] = Field(max_length=50)


# ---------------------------------------------------------------------------
# Webhook & sync
# ---------------------------------------------------------------------------


class HelloAssoWebhookPayload(BaseModel):
    """Payload pushed by HelloAsso to our webhook endpoint."""

    eventType: Literal["Order", "Payment", "Form"]
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


class WebhookConfigureIn(BaseModel):
    """Optional override of the URL registered against HelloAsso."""

    url: str | None = None


class WebhookStatusOut(BaseModel):
    """Etat du webhook HelloAsso, tel qu'on peut honnetement le connaitre.

    HelloAsso n'expose aucun moyen de relire l'URL de notification enregistree
    (``GET`` sur la route repond 405). ``configured`` ne peut donc pas etre
    affirme : le declarer ``false`` faisait passer un webhook parfaitement
    fonctionnel pour absent.

    ``last_sale_at`` est la seule preuve verifiable qu'il fonctionne : une vente
    recue est une notification que HelloAsso nous a bel et bien envoyee.
    """

    configured: bool | None = None
    verifiable: bool = False
    url: str | None = None
    # L'adresse a enregistrer chez HelloAsso, jeton compris. Servie meme
    # quand l'enregistrement automatique est impossible : c'est alors la
    # seule chose dont l'utilisateur a besoin, et la recopier de memoire
    # — avec un jeton de 43 caracteres — n'est pas envisageable.
    url_a_enregistrer: str | None = None
    # Vrai quand le compte n'est pas partenaire HelloAsso : l'API refuse
    # alors l'enregistrement (403), et il faut passer par leur interface.
    enregistrement_manuel_requis: bool = False
    last_sale_at: datetime | None = None
    sales_count: int = 0
    raw: dict[str, Any] | None = None


class SyncResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
