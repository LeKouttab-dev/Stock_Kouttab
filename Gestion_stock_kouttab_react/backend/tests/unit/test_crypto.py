"""Chiffrement au repos des champs sensibles (RIB).

Ce que ces tests protegent : le RIB est la donnee la plus sensible de la base
(§4 du CLAUDE.md). Jusqu'ici il y etait stocke en clair, protege par les seules
permissions applicatives — une copie de la base, une sauvegarde egaree ou un
acces MySQL suffisaient a repartir avec les coordonnees bancaires de tous les
benevoles.
"""

from __future__ import annotations

import base64
import os

import pytest

from app.core import crypto


CLE_ESSAI = base64.urlsafe_b64encode(bytes(range(32))).decode()
RIB_TYPE = "FR76 3000 6000 0112 3456 7890 189"


@pytest.fixture(autouse=True)
def cle_definie(monkeypatch: pytest.MonkeyPatch):
    """Chaque test part d'une cle connue, sans toucher au .env du poste."""
    monkeypatch.setattr(crypto, "_cle_cache", None, raising=False)
    monkeypatch.setenv("RIB_ENCRYPTION_KEY", CLE_ESSAI)
    yield
    crypto.reinitialiser_cle()


def test_aller_retour():
    chiffre = crypto.chiffrer(RIB_TYPE)
    assert chiffre != RIB_TYPE
    assert RIB_TYPE not in chiffre
    assert crypto.dechiffrer(chiffre) == RIB_TYPE


def test_deux_chiffrements_du_meme_rib_different():
    """Sans nonce distinct, deux comptes partageant un RIB seraient reperables
    a l'oeil nu dans un export de la base."""
    assert crypto.chiffrer(RIB_TYPE) != crypto.chiffrer(RIB_TYPE)


def test_valeur_heritee_en_clair_est_rendue_telle_quelle():
    """La base de production contient deja des RIB en clair : les lire ne doit
    pas echouer, sinon la page des notes de frais tombe le jour du deploiement."""
    assert crypto.dechiffrer(RIB_TYPE) == RIB_TYPE


def test_valeur_alteree_est_refusee():
    """AES-GCM authentifie : une modification directe en base doit se voir,
    et non produire un faux RIB silencieusement."""
    chiffre = crypto.chiffrer(RIB_TYPE)
    altere = chiffre[:-4] + ("AAAA" if not chiffre.endswith("AAAA") else "BBBB")
    with pytest.raises(crypto.ErreurDechiffrement):
        crypto.dechiffrer(altere)


def test_chiffrement_avec_une_autre_cle_est_illisible():
    chiffre = crypto.chiffrer(RIB_TYPE)
    crypto.reinitialiser_cle()
    os.environ["RIB_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
    with pytest.raises(crypto.ErreurDechiffrement):
        crypto.dechiffrer(chiffre)


def test_valeur_vide_et_none_traversent_sans_bruit():
    assert crypto.chiffrer(None) is None
    assert crypto.dechiffrer(None) is None
    assert crypto.chiffrer("") == ""
    assert crypto.dechiffrer("") == ""


def test_le_chiffre_tient_dans_la_colonne():
    """La colonne `Admins.rib` fait 255 caracteres et le schema est partage avec
    la base de production : le chiffrement ne doit pas imposer de migration."""
    long_rib = "FR76" + "9" * 30 + " BIC AGRIFRPP989"
    assert len(crypto.chiffrer(long_rib)) <= 255


def test_cle_absente_refuse_de_chiffrer(monkeypatch: pytest.MonkeyPatch):
    """Mieux vaut une erreur franche qu'un RIB ecrit en clair alors que
    l'exploitant croit le chiffrement actif."""
    from app.core.config import settings

    crypto.reinitialiser_cle()
    monkeypatch.delenv("RIB_ENCRYPTION_KEY", raising=False)
    # Les deux sources : la variable d'environnement ET le repli sur les
    # reglages, que `settings` a lus au chargement du module.
    monkeypatch.setattr(settings, "rib_encryption_key", "", raising=False)
    with pytest.raises(crypto.CleAbsente):
        crypto.chiffrer(RIB_TYPE)


def test_cle_de_mauvaise_taille_refusee(monkeypatch: pytest.MonkeyPatch):
    crypto.reinitialiser_cle()
    monkeypatch.setenv("RIB_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"trop court").decode())
    with pytest.raises(crypto.CleAbsente):
        crypto.chiffrer(RIB_TYPE)


def test_generer_cle_produit_une_cle_utilisable(monkeypatch: pytest.MonkeyPatch):
    nouvelle = crypto.generer_cle()
    crypto.reinitialiser_cle()
    monkeypatch.setenv("RIB_ENCRYPTION_KEY", nouvelle)
    assert crypto.dechiffrer(crypto.chiffrer(RIB_TYPE)) == RIB_TYPE
