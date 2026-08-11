"""Limiteur de debit partage.

Le ``Limiter`` vivait dans ``app.main``, ou les routers ne pouvaient pas
l'importer sans creer un cycle (``main`` importe ``api_router``). C'est la
raison pour laquelle aucun endpoint n'etait effectivement limite malgre le
middleware en place. On l'isole donc ici.

Limite : le backend applicatif est en memoire de process. Sur O2Switch, Passenger
peut lancer plusieurs workers, chacun avec son propre compteur — la limite reelle
est donc un multiple de celle annoncee. C'est acceptable pour freiner un
bruteforce, mais ce n'est pas une garantie stricte. Un backend Redis serait
necessaire pour cela (non disponible sur l'hebergement mutualise).
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
)
