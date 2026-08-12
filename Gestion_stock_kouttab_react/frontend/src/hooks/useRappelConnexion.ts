import { useEffect, useRef } from 'react';
import { usePendingSummary } from '@/api/endpoints/notifications';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/** Marque la session pour laquelle le rappel a déjà été montré. */
const CLE_SESSION = 'kouttab.rappel-connexion';

/**
 * Rappel affiché une fois par connexion : ce qui attend l'utilisateur.
 *
 * Les pastilles du menu disent déjà les chiffres, mais elles supposent qu'on
 * les regarde. Le rappel vient au-devant, au moment où l'on arrive.
 *
 * **Une fois par session, pas par page.** Sans cette mémoire, le rappel
 * reparaissait à chaque navigation — le contraire d'une notification, qui doit
 * signaler du nouveau. `sessionStorage` plutôt que `localStorage` : se
 * reconnecter le lendemain doit à nouveau prévenir.
 */
export function useRappelConnexion(): void {
  const { user } = useAuth();
  const { data: resume } = usePendingSummary();
  const toast = useToast();
  const dejaAffiche = useRef(false);

  useEffect(() => {
    if (!user || !resume || dejaAffiche.current) return;

    const marque = `${user.id}`;
    let dejaVu = false;
    try {
      dejaVu = sessionStorage.getItem(CLE_SESSION) === marque;
    } catch {
      // Stockage indisponible (navigation privée) : le rappel s'affichera à
      // chaque chargement plutôt que jamais. C'est le moindre mal.
    }
    if (dejaVu) return;

    dejaAffiche.current = true;
    try {
      sessionStorage.setItem(CLE_SESSION, marque);
    } catch {
      /* sans conséquence */
    }

    const rappels: Array<[number, string]> = [
      // En tête : c'est ce qu'on attend de MOI, avant ce que je dois traiter
      // pour les autres.
      [resume.justificatifs_demandes, fr.notifications.justificatifsDemandes],
      [resume.notes_a_valider, fr.notifications.notesAValider],
      [resume.factures_a_traiter, fr.notifications.facturesATraiter],
      [resume.modifications_stock, fr.notifications.modificationsStock],
      [resume.comptes_a_valider, fr.notifications.comptesAValider],
      [resume.articles_en_alerte, fr.notifications.articlesEnAlerte],
    ];

    const aSignaler = rappels.filter(([nombre]) => nombre > 0);
    if (aSignaler.length === 0) {
      // Rien à traiter : on ne dit rien. Une notification « vous n'avez rien à
      // faire » à chaque connexion deviendrait un bruit qu'on apprend à
      // ignorer, et ferait manquer les vraies.
      return;
    }

    toast.info(
      `${fr.notifications.bonjour} ${user.prenom || user.username}`,
      aSignaler.map(([nombre, libelle]) => `${nombre} ${libelle}`).join(' · '),
    );
  }, [user, resume, toast]);
}
