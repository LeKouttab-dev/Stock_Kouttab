import { useCallback, useEffect, useRef, useState } from 'react';
import type { FieldValues, UseFormReturn } from 'react-hook-form';

/**
 * Le formulaire de note de frais, conservé entre deux passages.
 *
 * Un bénévole sans RIB est renvoyé vers son profil au milieu de sa saisie, et
 * l'onglet qu'il quitte est **démonté** par Radix : il retrouvait un formulaire
 * vide et devait tout ressaisir. C'est cette perte que le brouillon supprime, et
 * elle vaut aussi pour une fenêtre fermée par erreur ou un téléphone qui se
 * verrouille.
 *
 * `localStorage` et non `sessionStorage` : « il revient plus tard » est
 * précisément le cas à couvrir, et une session meurt avec l'onglet.
 *
 * Ne sont conservées que les valeurs du formulaire. Les pièces jointes n'en font
 * pas partie : un `File` ne se sérialise pas, et recopier des justificatifs sur
 * la machine du bénévole pour un cas rare serait un mauvais échange.
 */

export const CLE_BROUILLON_NDF = 'kouttab.ndf.brouillon';

/**
 * Version du contenu enregistré. À incrémenter dès que la forme du formulaire
 * change : restaurer d'anciennes valeurs dans de nouveaux champs remplirait le
 * formulaire de travers, ce qui est pire que ne rien restaurer.
 */
const VERSION = 1;

/** Au-delà, on n'ouvre plus le tiroir : une saisie d'il y a trois mois déroute. */
const DUREE_MAX_MS = 7 * 24 * 60 * 60 * 1000;

/** Délai d'inactivité avant écriture — on n'écrit pas à chaque touche frappée. */
const DELAI_ECRITURE_MS = 400;

interface Enregistrement<T> {
  version: number;
  enregistre_le: number;
  valeurs: T;
}

interface Options {
  /** Le brouillon est cloisonné par compte : un poste partagé est un cas réel. */
  userId: number | null | undefined;
  /** Faux tant que le formulaire n'est pas prêt à être suivi. */
  actif?: boolean;
}

export interface Brouillon {
  /** Vrai si une saisie précédente a effectivement été remise dans le formulaire. */
  restaure: boolean;
  /** À appeler quand la note part : le brouillon n'a plus lieu d'être. */
  effacer: () => void;
}

/** Une saisie vide ne mérite pas d'être annoncée comme « restaurée ». */
function contientQuelqueChose(valeurs: unknown): boolean {
  if (!valeurs || typeof valeurs !== 'object') return false;
  return Object.values(valeurs as Record<string, unknown>).some((v) => {
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return v > 0;
    return false;
  });
}

export function useBrouillonNoteDeFrais<T extends FieldValues>(
  form: UseFormReturn<T>,
  { userId, actif = true }: Options,
): Brouillon {
  const cle = userId ? `${CLE_BROUILLON_NDF}.${userId}` : null;
  const [restaure, setRestaure] = useState(false);
  const minuteur = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suspendu = useRef(false);
  const enAttente = useRef<unknown>(null);

  const effacer = useCallback(() => {
    // Suspendu jusqu'à la prochaine saisie réelle : `form.reset()` suit l'envoi
    // et notifierait aussitôt le watch, qui réécrirait un brouillon vide.
    suspendu.current = true;
    enAttente.current = null;
    if (minuteur.current) clearTimeout(minuteur.current);
    if (!cle) return;
    try {
      localStorage.removeItem(cle);
    } catch {
      /* stockage indisponible : il n'y avait rien à effacer */
    }
  }, [cle]);

  // Restauration, une seule fois : rejouer un `reset` sur un formulaire déjà
  // rempli écraserait ce que le déposant vient de taper.
  const dejaRestaure = useRef(false);
  useEffect(() => {
    if (!cle || !actif || dejaRestaure.current) return;
    dejaRestaure.current = true;

    let brut: string | null = null;
    try {
      brut = localStorage.getItem(cle);
    } catch {
      return; // navigation privée : pas de brouillon, et ce n'est pas une erreur
    }
    if (!brut) return;

    let enregistrement: Enregistrement<T> | null = null;
    try {
      enregistrement = JSON.parse(brut) as Enregistrement<T>;
    } catch {
      effacer();
      return;
    }

    const perime = Date.now() - (enregistrement?.enregistre_le ?? 0) > DUREE_MAX_MS;
    if (enregistrement?.version !== VERSION || perime) {
      effacer();
      return;
    }
    if (!contientQuelqueChose(enregistrement.valeurs)) return;

    form.reset(enregistrement.valeurs);
    setRestaure(true);
    suspendu.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle, actif]);

  useEffect(() => {
    if (!cle || !actif) return;

    const ecrire = (valeurs: unknown) => {
      enAttente.current = null;
      if (!contientQuelqueChose(valeurs)) return;
      const enregistrement: Enregistrement<unknown> = {
        version: VERSION,
        enregistre_le: Date.now(),
        valeurs,
      };
      try {
        localStorage.setItem(cle, JSON.stringify(enregistrement));
      } catch {
        /* quota atteint ou stockage refusé : la saisie continue sans filet */
      }
    };

    const abonnement = form.watch((valeurs) => {
      if (suspendu.current) {
        // La première notification après un envoi vient du `reset` lui-même.
        if (contientQuelqueChose(valeurs)) suspendu.current = false;
        else return;
      }
      enAttente.current = valeurs;
      if (minuteur.current) clearTimeout(minuteur.current);
      minuteur.current = setTimeout(() => ecrire(valeurs), DELAI_ECRITURE_MS);
    });

    return () => {
      abonnement.unsubscribe();
      if (minuteur.current) clearTimeout(minuteur.current);
      // Le démontage ÉCRIT ce qui attendait au lieu de le jeter : c'est
      // exactement le moment ou le formulaire disparait — onglet quitté pour
      // aller déposer son RIB — et la derniere frappe serait perdue.
      if (enAttente.current !== null) ecrire(enAttente.current);
    };
  }, [cle, actif, form]);

  return { restaure, effacer };
}
