"""La famille d'un evenement se lit dans son titre HelloAsso.

L'association ecrit la lettre entre parentheses en fin d'intitule — « Sortie
pedagogique a la ferme (J) ». C'est cette lettre qui decide sous quel pole EV la
piece est rattachee au depot.

Elle etait auparavant **saisie a la main** : tout evenement importe arrivait
sans famille, et le restait jusqu'a ce que quelqu'un pense a ouvrir l'ecran
d'administration. Entre-temps il apparaissait sous les trois poles EV, et rien
n'empechait de rattacher une depense (J) au pole EV(T).

Les huit evenements en base au 2026-08-31 respectent tous la convention.
"""

from __future__ import annotations

import pytest

from app.crud.event import SOURCE_HELLOASSO, SOURCE_MANUAL, deduire_type_ev
from app.crud.event import sync_events_from_helloasso
from app.db.models import Event


pytestmark = pytest.mark.unit


# Les huit intitules reellement presents en production, plus les cas limites.
@pytest.mark.parametrize(
    "titre, attendu",
    [
        ("21/08 - Cafe debat : La mise en relation des pretendants (G)", "G"),
        ("15/08 - Randonnee du kouttab (G)", "G"),
        # Espaces en fin de titre : presents en base, ils ne doivent rien casser.
        ("16/08 - Sortie pedagogique a la ferme (J)  ", "J"),
        ("14/08 Atelier Histoire - A la decouverte d'Al Khidr (J)  ", "J"),
        ("Aout 26 - Stage de Qur'an Hommes (T)", "T"),
        ("06/09 - Journee decouverte du Kouttab (T)", "T"),
        # Minuscule : la convention est en majuscule, mais une faute de frappe
        # ne doit pas faire perdre la famille.
        ("Repas de fin d'annee (t)", "T"),
        # Une parenthese anterieure ne doit pas voler la place : la lettre est
        # une etiquette de fin de titre, c'est la derniere qui compte.
        ("Atelier (gratuit) ouvert aux jeunes (J)", "J"),
        ("Sortie (T) puis veillee (G)", "G"),
    ],
)
def test_la_lettre_du_titre_donne_la_famille(titre, attendu):
    assert deduire_type_ev(titre) == attendu


@pytest.mark.parametrize(
    "titre",
    [
        "Evenement sans etiquette",
        "Reunion (A)",  # une lettre hors T/G/J n'est pas une famille
        "Conference (TG)",  # deux lettres non plus
        "",
        None,
    ],
)
def test_un_titre_sans_lettre_ne_classe_rien(titre):
    """`None`, et non un repli arbitraire.

    Un evenement non classe reste propose sous TOUS les poles EV. Le ranger
    d'office sous l'un d'eux le rendrait invisible sous les deux autres — pire
    qu'une proposition trop large, qui elle se corrige d'un coup d'oeil.
    """
    assert deduire_type_ev(titre) is None


def test_la_synchronisation_classe_les_evenements_crees(db_session):
    """Le defaut d'origine : tout evenement importe arrivait sans famille."""
    sync_events_from_helloasso(
        db_session,
        [
            {"formSlug": "ferme", "formType": "Event", "title": "Sortie a la ferme (J)"},
            {"formSlug": "stage", "formType": "Event", "title": "Stage de Qur'an (T)"},
            {"formSlug": "libre", "formType": "Event", "title": "Evenement non etiquete"},
        ],
    )

    familles = {
        e.helloasso_form_slug: e.type_ev
        for e in db_session.query(Event).filter(Event.source == SOURCE_HELLOASSO)
    }
    assert familles == {"ferme": "J", "stage": "T", "libre": None}


def test_un_titre_corrige_chez_helloasso_redescend(db_session):
    """La famille suit le titre, sans intervention.

    C'est le point de la manoeuvre : corriger l'etiquette se fait la ou
    l'association ecrit deja, et non dans un second ecran qu'il faut penser a
    ouvrir.
    """
    sync_events_from_helloasso(
        db_session, [{"formSlug": "gala", "formType": "Event", "title": "Gala (T)"}]
    )
    sync_events_from_helloasso(
        db_session, [{"formSlug": "gala", "formType": "Event", "title": "Gala (G)"}]
    )

    event = db_session.query(Event).filter(Event.helloasso_form_slug == "gala").one()
    assert event.type_ev == "G"


def test_un_titre_sans_lettre_n_efface_pas_le_classement_a_la_main(db_session):
    """Sinon l'etiquette posee a la main sauterait a la synchronisation suivante.

    Le titre fait autorite **quand il porte la lettre**. Quand il n'en porte
    pas, il n'a rien a dire — et surtout pas a effacer ce que quelqu'un a
    renseigne en connaissance de cause.
    """
    sync_events_from_helloasso(
        db_session, [{"formSlug": "atelier", "formType": "Event", "title": "Atelier libre"}]
    )
    event = db_session.query(Event).filter(Event.helloasso_form_slug == "atelier").one()
    event.type_ev = "G"
    db_session.commit()

    sync_events_from_helloasso(
        db_session, [{"formSlug": "atelier", "formType": "Event", "title": "Atelier libre"}]
    )

    db_session.refresh(event)
    assert event.type_ev == "G"


def test_un_evenement_manuel_reste_intouche(db_session):
    """Regle deja en place, reverifiee ici : la deduction ne doit pas la percer.

    Un evenement saisi a la main porte un intitule choisi par l'association pour
    ses propres besoins ; le classer d'apres une parenthese serait une surprise.
    """
    manuel = Event(
        helloasso_form_slug="atelier",
        helloasso_form_type="Event",
        nom="Atelier saisi a la main (T)",
        source=SOURCE_MANUAL,
        type_ev=None,
        is_active=True,
    )
    db_session.add(manuel)
    db_session.commit()

    sync_events_from_helloasso(
        db_session,
        [{"formSlug": "atelier", "formType": "Event", "title": "Atelier renomme (G)"}],
    )

    db_session.refresh(manuel)
    assert manuel.type_ev is None
    assert manuel.nom == "Atelier saisi a la main (T)"


# ---- Cadence de la synchronisation quotidienne -------------------------------


def test_la_synchronisation_quotidienne_se_tait_si_elle_vient_de_passer(
    db_session, monkeypatch
):
    """Le worker passe toutes les 10 min : sans garde, HelloAsso serait appele
    144 fois par jour pour un referentiel qui bouge une fois par semaine.

    Aucune table d'ordonnancement : `last_synced_at` porte deja la date du
    dernier passage.
    """
    import scripts.process_outbound_emails as cron

    sync_events_from_helloasso(
        db_session, [{"formSlug": "gala", "formType": "Event", "title": "Gala (T)"}]
    )

    def _interdit(*args, **kwargs):  # pragma: no cover — ne doit jamais courir
        raise AssertionError("HelloAsso appele alors que la synchronisation est recente")

    monkeypatch.setattr(cron, "get_helloasso_client", _interdit)
    monkeypatch.setattr(cron, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    assert cron.synchroniser_les_evenements() is None


def test_la_synchronisation_repart_passe_le_delai(db_session, monkeypatch):
    """20 heures et non 24 : a 24 le passage glisse chaque jour et finit par
    sauter une journee entiere."""
    import scripts.process_outbound_emails as cron

    sync_events_from_helloasso(
        db_session, [{"formSlug": "gala", "formType": "Event", "title": "Gala (T)"}]
    )
    vieux = db_session.query(Event).filter(Event.helloasso_form_slug == "gala").one()
    vieux.last_synced_at = vieux.last_synced_at - cron.INTERVALLE_SYNC_EVENEMENTS
    db_session.commit()

    class _Client:
        def list_organization_forms(self, *args, **kwargs):
            return [{"formSlug": "gala", "formType": "Event", "title": "Gala renomme (G)"}]

    monkeypatch.setattr(cron, "get_helloasso_client", lambda: _Client())
    monkeypatch.setattr(cron, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = cron.synchroniser_les_evenements()

    assert resultat is not None and resultat["updated"] == 1
    db_session.refresh(vieux)
    assert vieux.type_ev == "G"


def test_une_panne_helloasso_ne_tue_pas_la_file_comptable():
    """HelloAsso est un tiers : il tombe, et il change ses reponses.

    La synchronisation a son propre garde-fou. Sous celui de la file, une panne
    de leur cote empecherait un courriel comptable de partir — la file etant
    traitee en premier, l'exception remonterait apres coup et masquerait tout ce
    qui suit.
    """
    import inspect

    import scripts.process_outbound_emails as cron

    bloc = inspect.getsource(cron.main).split("if not args.skip_events:")[1]
    assert "try:" in bloc and "except Exception" in bloc
