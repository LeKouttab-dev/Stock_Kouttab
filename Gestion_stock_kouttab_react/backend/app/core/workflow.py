"""Transitions de statut autorisees pour les factures et les notes de frais.

Les statuts etaient auparavant affectes sans aucun controle : une note
``Remboursee`` pouvait repasser ``En attente``, et rien n'empechait de sauter
des etapes. Pour des pieces comptables, cela rend l'historique ininterpretable.

Le graphe reste volontairement permissif sur les corrections (on peut revenir
d'``Approuvee`` vers ``En attente`` en cas d'erreur de saisie) mais ferme les
etats terminaux.
"""

from __future__ import annotations

from app.core.errors import ErrorCode
from app.core.exceptions import AppException


# Factures : le circuit normal est En attente -> En cours -> Validee.
INVOICE_TRANSITIONS: dict[str, set[str]] = {
    "En attente": {"En cours de traitement", "Validée", "Refusée"},
    "En cours de traitement": {"Validée", "Refusée", "En attente"},
    "Validée": set(),  # terminal : une facture validee est comptabilisee
    "Refusée": {"En attente"},  # rouvrable si le deposant corrige sa piece
}

# Notes de frais : En attente -> Approuvee -> Remboursee.
#
# « Remboursee » ne figure dans AUCUNE cible : ce statut ne se declare pas, il
# se constate. On l'atteint par `POST /reimbursements`, qui enregistre le
# versement — date, moyen, etablissement, approbation — et produit le
# justificatif. La liste deroulante de l'ecran comptable y menait aussi, sans
# rien produire : des notes se retrouvaient marquees payees, sans document, et
# le statut etant terminal, sans aucun moyen de corriger.
EXPENSE_TRANSITIONS: dict[str, set[str]] = {
    "En attente": {"Approuvée", "Refusée"},
    "Approuvée": {"Refusée", "En attente"},
    # Porte de sortie pour les notes marquees a tort, avant que ce chemin ne
    # soit ferme. `crud.expense.validate_expense` la refuse des qu'un versement
    # est rattache : revenir en arriere contredirait un justificatif emis.
    "Remboursée": {"Approuvée"},
    "Refusée": {"En attente"},
}


def _check(
    transitions: dict[str, set[str]], current: str, new: str, *, label: str
) -> None:
    if current == new:
        return
    allowed = transitions.get(current)
    if allowed is None:
        # Statut inconnu en base (donnee legacy) : on laisse passer plutot que
        # de bloquer un utilisateur sur une ligne historique mal formee.
        return
    if new not in allowed:
        readable = ", ".join(sorted(allowed)) or "aucun"
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=(
                f"Transition de statut interdite pour {label} : "
                f"'{current}' -> '{new}'. Transitions possibles : {readable}."
            ),
            extras={"from": current, "to": new, "allowed": sorted(allowed)},
        )


def check_invoice_transition(current: str, new: str) -> None:
    _check(INVOICE_TRANSITIONS, current, new, label="une facture")


def check_expense_transition(current: str, new: str) -> None:
    _check(EXPENSE_TRANSITIONS, current, new, label="une note de frais")
