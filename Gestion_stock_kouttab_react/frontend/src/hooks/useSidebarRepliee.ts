import { useCallback, useState } from 'react';
import { estPleineLargeur } from '@/lib/layout';

export type ModeSidebar = 'auto' | 'ouverte' | 'repliee';

const CLE = 'layout.sidebar';

function lire(): ModeSidebar {
  try {
    const brut = localStorage.getItem(CLE);
    return brut === 'ouverte' || brut === 'repliee' ? brut : 'auto';
  } catch {
    // Navigation privée, stockage plein : la barre doit fonctionner quand même.
    return 'auto';
  }
}

function ecrire(mode: ModeSidebar) {
  try {
    if (mode === 'auto') localStorage.removeItem(CLE);
    else localStorage.setItem(CLE, mode);
  } catch {
    /* sans effet, et sans conséquence */
  }
}

/**
 * Replier la barre latérale, avec un défaut qui dépend de la page.
 *
 * Le piège de « repliée par défaut sur le calendrier » est l'effet qui
 * re-replie à chaque navigation et se bat contre le clic de l'utilisateur. On
 * l'évite en **ne mettant aucun effet** : l'état est dérivé, pas synchronisé.
 *
 * | Mémorisé | Sur `/calendar` | Ailleurs |
 * |---|---|---|
 * | rien (`auto`) | repliée | dépliée |
 * | `ouverte` | dépliée | dépliée |
 * | `repliee` | repliée | repliée |
 *
 * Le premier clic fait sortir de `auto`, et la préférence devient globale. Dès
 * que quelqu'un a exprimé un choix, on ne décide plus pour lui — c'est ce qui
 * empêche le réglage d'être agaçant.
 *
 * On ne mémorise que le non-défaut, comme pour les agendas masqués et les
 * groupes de produits repliés.
 */
export function useSidebarRepliee(chemin: string) {
  const [mode, setMode] = useState<ModeSidebar>(lire);

  const repliee = mode === 'auto' ? estPleineLargeur(chemin) : mode === 'repliee';

  const basculer = useCallback(() => {
    const suivant: ModeSidebar = repliee ? 'ouverte' : 'repliee';
    ecrire(suivant);
    setMode(suivant);
  }, [repliee]);

  return { repliee, basculer };
}
