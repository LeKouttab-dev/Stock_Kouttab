"""Auth-related Pydantic schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.calendar import AgendaOut, EvenementOut
from app.schemas.user import UserOut


ROLE_LITERAL = Literal[
    "Super Admin", "AdminBenevoles", "Compta", "Benevole", "BenevoleFrais", "AdminStock"
]


class LoginIn(BaseModel):
    """Identifiant **ou** adresse e-mail.

    La borne haute etait celle d'un identifiant (20 caracteres) : une adresse
    e-mail etait donc rejetee en 422 « Donnees invalides » avant meme d'etre
    cherchee en base, sans que rien n'indique pourquoi. Cf. `get_user_by_login`.
    """

    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class ForgotPasswordIn(BaseModel):
    """Identifiant **ou** adresse e-mail, comme a la connexion."""

    identifiant: str = Field(min_length=3, max_length=254)


class SsoExchangeIn(BaseModel):
    """Jeton de passage émis par gestion.lekouttab.fr (transmis en fragment #)."""

    token: str = Field(min_length=20, max_length=2048)


class SsoDepenseOut(BaseModel):
    """Une note de frais telle que l'outil de gestion la lit pour son bilan.

    Volontairement pauvre : l'identifiant, de quoi afficher la ligne, et de quoi
    la totaliser. Ni email, ni commentaire, ni justificatif — le bilan d'un
    événement n'en a pas besoin, et ce qui ne traverse pas la frontière ne peut
    pas fuir.

    Les montants sont des **chaînes** et non des flottants : ce sont des
    `DECIMAL(10,2)` des deux côtés, et un passage par `float` perdrait des
    centimes sur des sommes de plusieurs dizaines de lignes.
    """

    id: int
    libelle: str
    montant: str
    remise: str
    statut: str
    date_depense: date | None = None
    fournisseur: str | None = None
    categorie: str | None = None
    demandeur: str | None = None


class SsoDepensesOut(BaseModel):
    """`evenement_trouve` distingue « aucune dépense » de « événement inconnu ».

    Les deux rendent une liste vide — jamais une erreur, qui ferait de
    l'endpoint un test d'existence pour qui tient le secret partagé — mais
    l'outil de gestion peut ainsi le signaler différemment.
    """

    evenement_trouve: bool
    lignes: list[SsoDepenseOut]


class SsoCalendrierOut(BaseModel):
    """Le calendrier tel que l'outil de gestion le lit.

    Les agendas accompagnent les evenements : sans eux, le selecteur de
    l'autre outil ne pourrait pas proposer un agenda qui n'a rien cette
    semaine-la, et il disparaitrait de la liste une semaine sur deux.

    **Les agendas reserves n'en font jamais partie** — quel que soit le
    demandeur. Ils restent consultables dans cette application, par un Super
    Admin ; les faire traverser la frontiere reviendrait a confier leur
    filtrage a l'autre outil.
    """

    agendas: list[AgendaOut]
    evenements: list[EvenementOut]
    # Releve fige : l'ecran de gestion doit pouvoir le dire comme le notre.
    instantane: bool = False
    genere_le: str | None = None


class SsoProduitLaitOut(BaseModel):
    id: int
    nom: str
    actif: bool


class SsoBuvetteLaitOut(BaseModel):
    """Etat des boissons au lait de la buvette, lu ou bascule par gestion.

    `actif` est vrai quand TOUTES sont proposees sur la tablette : un etat
    mixte (l'une reactivee a la main ici) s'affiche donc « desactivees » la-bas,
    et un clic sur « activer » les remet toutes d'accord.
    """

    actif: bool
    produits: list[SsoProduitLaitOut]


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    password_must_change: bool = False
    # Nom de l'operateur d'une session tablette (null pour toute autre session).
    operateur: str | None = None


class MeOut(UserOut):
    """`GET /auth/me` : l'utilisateur, plus l'operateur d'une session tablette."""

    operateur: str | None = None


class CaisseSessionIn(BaseModel):
    """`POST /auth/caisse/session` : le nom saisi sur la tablette (2 a 60 caracteres, nettoye)."""

    operateur: str = Field(max_length=200)

    @field_validator("operateur")
    @classmethod
    def _nettoyer(cls, valeur: str) -> str:
        from pydantic_core import PydanticCustomError

        from app.core.tablette import nettoyer_operateur

        try:
            return nettoyer_operateur(valeur)
        except ValueError as exc:
            # Erreur « personnalisee » : un ValueError brut finirait dans `ctx`
            # de la reponse 422, que le gestionnaire ne sait pas serialiser.
            raise PydanticCustomError("operateur_invalide", str(exc)) from None


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    """Corps optionnel : sans refresh token, toutes les sessions sont revoquees."""

    refresh_token: str | None = None


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupIn(BaseModel):
    """Public signup payload.

    Le role n'est volontairement PAS acceptable en entree : un demandeur
    pouvait sinon s'auto-attribuer ``Super Admin``, qu'un valideur pressé
    n'aurait pas forcement remarque en approuvant le compte. Tout compte cree
    ici est ``Benevole`` ; la promotion passe par ``PATCH /users/{id}/role``.
    """

    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=200)
    confirm_password: str | None = None
    nom: str | None = None
    prenom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None


class AdminSetupIn(BaseModel):
    email: EmailStr
    token: str
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=200)
    nom: str | None = None
    prenom: str | None = None


class InvitationValidateOut(BaseModel):
    valid: bool
    message: str
    email: EmailStr | None = None


class MessageOut(BaseModel):
    message: str
