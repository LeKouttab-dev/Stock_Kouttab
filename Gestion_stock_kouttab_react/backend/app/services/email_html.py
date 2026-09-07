"""Version HTML des courriels, deduite du texte brut.

Les gabarits ecrivent du texte, et continuent : leur corps est la version lue
par les clients qui ne rendent pas le HTML, il est celui qu'on relit dans
l'ecran « Envois » de l'administration, et c'est le seul format qui survive a un
copier-coller. Rien ici ne leur demande de changer.

Ce module en fabrique le pendant HTML au moment de l'envoi, pour une raison
precise : **l'adresse de l'application ne se cliquait pas de facon fiable**. Une
URL nue dans un message en texte seul depend du bon vouloir du client de
messagerie — certains la coupent au premier retour a la ligne, d'autres ne la
detectent pas du tout — et le lecteur se retrouve a recopier un domaine a la
main. Un `<a>` explicite, lui, est un bouton.

**Ce que ce module NE fait PAS** : forcer l'ouverture dans le navigateur du
systeme. Aucun format de courriel ne le permet ; l'application Gmail sur mobile
ouvre les liens dans sa propre vue integree, et c'est un reglage du lecteur
(« Ouvrir les liens web dans Gmail »), pas de l'expediteur. `target="_blank"`
garantit seulement qu'un webmail ouvre un nouvel onglet plutot que de remplacer
la boite de reception.
"""

from __future__ import annotations

import re
from html import escape


# Une ligne « libelle    : valeur » produite par `email_layout.details`. Le
# remplissage aligne les valeurs en texte brut ; en HTML il n'a plus de sens —
# la police n'est pas a chasse fixe — et laisserait une suite d'espaces avant
# les deux-points. On recupere donc les deux moitiés pour les remettre dans un
# tableau, qui aligne pour de bon.
_DETAIL = re.compile(r"^(\S[^:]{0,60}?)\s*:[ \t](.*)$")

# La ligne d'acces posee par `liens.avec_lien` / `liens.garantir_lien`. Elle
# devient le bouton du message : c'est le geste qu'on attend du lecteur.
_ACCES = re.compile(r"^(Acceder a [^:]+?)\s*:\s*(https?://\S+)$")

_URL = re.compile(r"https?://[^\s<>\"']+")

# Ponctuation finale a ne pas avaler dans l'URL : « ...voir https://x/y. » ne
# doit pas produire un lien vers « y. ».
_PONCTUATION_FINALE = ".,;:!?)»\"'"

_STYLE_LIEN = "color:#0f766e;text-decoration:underline;"
_STYLE_BOUTON = (
    "display:inline-block;padding:12px 22px;background:#0f766e;color:#ffffff;"
    "text-decoration:none;border-radius:6px;font-weight:600;"
)


def _lien(url: str, *, texte: str | None = None, style: str = _STYLE_LIEN) -> str:
    """Ancre vers `url`, ouverte dans un nouvel onglet.

    `rel="noopener noreferrer"` va avec `target="_blank"` : sans lui, la page
    ouverte garde une poignee sur celle qui l'a ouverte.
    """
    cible = escape(url, quote=True)
    return (
        f'<a href="{cible}" target="_blank" rel="noopener noreferrer" '
        f'style="{style}">{escape(texte or url)}</a>'
    )


def _lier_les_urls(texte_echappe: str, texte_source: str) -> str:
    """Remplace les URL d'un fragment DEJA echappe par des ancres."""
    resultat: list[str] = []
    position = 0
    for trouve in _URL.finditer(texte_source):
        url = trouve.group(0).rstrip(_PONCTUATION_FINALE)
        avant = escape(texte_source[position : trouve.start()])
        resultat.append(avant)
        resultat.append(_lien(url))
        resultat.append(escape(trouve.group(0)[len(url) :]))
        position = trouve.end()
    if not resultat:
        return texte_echappe
    resultat.append(escape(texte_source[position:]))
    return "".join(resultat)


def _bloc_details(lignes: list[str]) -> str | None:
    """Rend un tableau si TOUTES les lignes sont des « libelle : valeur ».

    Le tout ou rien est volontaire : un bloc mi-phrase mi-details deviendrait un
    tableau bancal ou la phrase occuperait une cellule de libelle.
    """
    paires = [_DETAIL.match(ligne) for ligne in lignes]
    if len(lignes) < 2 or not all(paires):
        return None
    cellules = "".join(
        "<tr>"
        f'<td style="padding:3px 14px 3px 0;color:#57534e;white-space:nowrap;'
        f'vertical-align:top;">{escape(p.group(1).strip())}</td>'
        f'<td style="padding:3px 0;color:#1c1917;">'
        f"{_lier_les_urls(escape(p.group(2)), p.group(2))}</td>"
        "</tr>"
        for p in paires
        if p is not None
    )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:16px 0;font-size:14px;">{cellules}</table>'
    )


def _bloc_acces(lignes: list[str]) -> str | None:
    """Rend le bouton d'acces quand le bloc n'est que la ligne de lien."""
    if len(lignes) != 1:
        return None
    trouve = _ACCES.match(lignes[0])
    if not trouve:
        return None
    return (
        '<div style="margin:24px 0;">'
        f"{_lien(trouve.group(2), texte=trouve.group(1).strip(), style=_STYLE_BOUTON)}"
        "</div>"
    )


def _paragraphe(lignes: list[str]) -> str:
    contenu = "<br>".join(_lier_les_urls(escape(l), l) for l in lignes)
    return f'<p style="margin:12px 0;">{contenu}</p>'


def en_html(corps: str) -> str:
    """Rend la version HTML d'un corps de courriel ecrit en texte brut."""
    blocs = [b for b in re.split(r"\n[ \t]*\n", corps.replace("\r\n", "\n"))]
    morceaux: list[str] = []
    for bloc in blocs:
        lignes = [l.rstrip() for l in bloc.split("\n") if l.strip()]
        if not lignes:
            continue
        morceaux.append(
            _bloc_acces(lignes) or _bloc_details(lignes) or _paragraphe(lignes)
        )
    return (
        '<div style="margin:0;padding:24px 12px;background:#f5f5f4;">'
        '<div style="max-width:600px;margin:0 auto;padding:28px 32px;'
        "background:#ffffff;border-radius:10px;color:#1c1917;font-size:15px;"
        "line-height:1.6;font-family:-apple-system,BlinkMacSystemFont,"
        "'Segoe UI',Roboto,Helvetica,Arial,sans-serif;\">"
        + "".join(morceaux)
        + "</div></div>"
    )


__all__ = ["en_html"]
