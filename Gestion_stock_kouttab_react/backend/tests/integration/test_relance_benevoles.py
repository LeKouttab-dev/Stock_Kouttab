"""Relance ponctuelle des bénévoles.

Le script écrit à de vraies personnes : il ne doit **rien** envoyer sans qu'on le
lui demande explicitement, et ne doit viser que ceux qu'il annonce. Ces deux
propriétés sont l'essentiel de ce qui est testé ici.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts import relancer_benevoles as relance  # noqa: E402

from app.crud import expense as expense_crud
from app.db.models import OutboundEmail
from app.services import outbox


def _note_commentee(db_session, user, commentaire="Précisez le nombre de repas."):
    note = expense_crud.create_expense(
        db_session,
        user_id=user.id,
        date_depense=date(2026, 6, 12),
        rattachement="Frais généraux",
        fournisseur="Carrefour",
        nature_charge="Courses",
        montant=Decimal("42.90"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
    )
    note.commentaires_compta = commentaire
    note.non_lu_demandeur = True
    db_session.commit()
    return note


def _envois(db_session):
    return db_session.execute(select(OutboundEmail)).scalars().all()


def _depouiller(db_session, compte, *, iban: bool, document: bool) -> None:
    """Pose l'etat exact du compte : IBAN present ou non, document present ou non."""
    compte.rib = "FR7612345678901234567890123" if iban else None
    compte.rib_document_nom = "rib.pdf" if document else None
    compte.rib_document_type = "application/pdf" if document else None
    db_session.commit()


def test_la_simulation_n_envoie_rien(db_session, benevole_user, capsys):
    """Le garde-fou principal : `--envoyer` absent, rien ne part."""
    _depouiller(db_session, benevole_user, iban=False, document=False)

    relance.relancer_rib(db_session, [benevole_user], envoyer=False)

    assert _envois(db_session) == []
    # ...mais la personne visée est bien nommée, pour qu'on relise la liste.
    assert benevole_user.username in capsys.readouterr().out


def test_l_envoi_passe_par_la_file(db_session, benevole_user):
    _depouiller(db_session, benevole_user, iban=False, document=False)

    relance.relancer_rib(db_session, [benevole_user], envoyer=True)

    envois = _envois(db_session)
    assert len(envois) == 1
    assert envois[0].kind == relance.KIND_RIB
    # Par la file : visible dans l'écran d'administration, et relançable.
    assert envois[0].status == outbox.STATUS_PENDING


def test_un_compte_complet_n_est_pas_relance(db_session, benevole_user):
    """L'IBAN **et** le document : c'est ce que le dépôt exige, donc la condition."""
    _depouiller(db_session, benevole_user, iban=True, document=True)

    assert relance.relancer_rib(db_session, [benevole_user], envoyer=True) == 0
    assert _envois(db_session) == []


def test_le_document_sans_iban_est_relance(db_session, benevole_user):
    """Le cas qui échappait à la relance, et que le dépôt refuse pourtant.

    Le critère portait sur l'absence des DEUX : celui qui avait déposé sa photo
    sans jamais saisir son IBAN n'était donc jamais relancé — bloqué au dépôt,
    et sans rien pour le lui apprendre. C'est la plainte du 2026-09-07.
    """
    _depouiller(db_session, benevole_user, iban=False, document=True)

    assert relance.relancer_rib(db_session, [benevole_user], envoyer=True) == 1
    # Et le courriel nomme ce qui manque : réclamer le document à quelqu'un qui
    # l'a déjà déposé le fait redéposer la même photo en boucle.
    corps = _envois(db_session)[0].body
    assert "IBAN" in corps


def test_l_iban_sans_document_est_relance(db_session, benevole_user):
    _depouiller(db_session, benevole_user, iban=True, document=False)

    assert relance.relancer_rib(db_session, [benevole_user], envoyer=True) == 1
    assert "document" in _envois(db_session)[0].body


def test_un_document_reste_en_image_ne_vaut_pas_document(db_session, benevole_user):
    """Même critère de format que le dépôt : un nom de fichier ne prouve rien.

    Relancer sur un critère plus laxiste que celui qui bloque revient à
    promettre que tout va bien à quelqu'un qui sera arrêté cinq minutes plus
    tard.
    """
    _depouiller(db_session, benevole_user, iban=True, document=True)
    benevole_user.rib_document_type = "image/png"
    db_session.commit()

    assert relance.relancer_rib(db_session, [benevole_user], envoyer=True) == 1


def test_une_seule_relance_par_personne(db_session, benevole_user):
    """Un courriel par note noierait le message chez qui en a plusieurs — et
    c'est précisément celui-là qu'il faut atteindre."""
    _note_commentee(db_session, benevole_user, "Précisez la date.")
    _note_commentee(db_session, benevole_user, "Le ticket est illisible.")

    assert relance.relancer_commentaires(db_session, [benevole_user], envoyer=True) == 1

    envois = _envois(db_session)
    assert len(envois) == 1
    # Les deux commentaires figurent dans le message : sinon la personne doit
    # ouvrir l'application pour savoir de quoi il retourne.
    assert "Précisez la date." in envois[0].body
    assert "Le ticket est illisible." in envois[0].body


def test_un_commentaire_deja_lu_ne_relance_pas(db_session, benevole_user):
    note = _note_commentee(db_session, benevole_user)
    note.non_lu_demandeur = False
    db_session.commit()

    assert relance.relancer_commentaires(db_session, [benevole_user], envoyer=True) == 0


def test_la_selection_par_nom_ecarte_les_autres(
    db_session, benevole_user, admin_benevoles_user
):
    for compte in (benevole_user, admin_benevoles_user):
        compte.rib = None
        compte.rib_document_nom = None
    db_session.commit()

    retenus = relance._comptes_actifs(db_session, [benevole_user.username])

    assert [c.id for c in retenus] == [benevole_user.id]


def test_un_nom_inconnu_est_signale(db_session, benevole_user, caplog, monkeypatch):
    """Une faute de frappe ne doit pas se lire comme « personne à relancer »."""
    traces: list[str] = []
    monkeypatch.setattr(
        relance.logger,
        "warning",
        lambda message, *args, **_: traces.append(message % args if args else message),
    )

    relance._comptes_actifs(db_session, ["nexiste.pas"])

    assert "nexiste.pas" in "\n".join(traces)


def test_un_compte_sans_adresse_est_ecarte(db_session, benevole_user):
    """Il n'est pas relançable ; le mettre en file laisserait une ligne
    éternellement en attente."""
    benevole_user.email = None
    db_session.commit()

    retenus = relance._comptes_actifs(db_session, [])

    assert benevole_user.id not in [c.id for c in retenus]
