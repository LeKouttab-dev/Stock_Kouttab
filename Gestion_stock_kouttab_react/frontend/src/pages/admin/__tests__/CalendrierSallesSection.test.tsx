import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { Agenda, ReglagesAgendas, SalleDeduite } from '@/types/api';

/**
 * Ranger les agendas dans les salles.
 *
 * Deux propriétés valent d'être verrouillées, et ce sont les deux qui
 * protègent de l'écran qui ment :
 *
 *  1. **Un seul PUT, et seulement les lignes touchées.** Un remplacement
 *     global effacerait les trente-cinq agendas qu'on n'a pas regardés.
 *  2. **« Proposer d'après Google » n'enregistre rien.** La déduction remplit
 *     le formulaire ; c'est une personne qui décide qu'un cours se tient dans
 *     telle salle.
 */

const AGENDAS: Agenda[] = [
  {
    id: 'coran@g',
    nom: 'Coran - enfants 1 U.soundousse 2026/2027',
    restreint: false,
    nom_court: 'Coran ENF 1',
    enseignant: 'U. Soundousse',
    salle_par_defaut: null,
    categorie: 'Coran',
    sous_categorie: 'Coran enfants',
    categorie_rang: 0,
  },
  {
    id: 'si@g',
    nom: 'SI - Adorations 2026/2027',
    restreint: false,
    nom_court: 'SI Adorations',
    enseignant: null,
    salle_par_defaut: null,
    categorie: 'Sciences islamiques',
    sous_categorie: null,
    categorie_rang: 1,
  },
];

const SALLES = {
  maziri: 'Imam Maziri',
  nafi: "Imam Nafi'",
  zarrouq: 'Imam Zarrouq',
};

const REGLAGES: ReglagesAgendas = { reglages: [], salles: SALLES };

const DEDUCTION: SalleDeduite[] = [
  {
    agenda_id: 'si@g',
    agenda_nom: 'SI - Adorations 2026/2027',
    salle: 'maziri',
    occurrences: 8,
    total_evenements: 9,
  },
];

const enregistrer = vi.fn();
const refetchDeduction = vi.fn();

vi.mock('@/api/endpoints/calendar', () => ({
  useAgendas: () => ({ data: AGENDAS, isLoading: false }),
  useReglagesAgendas: () => ({ data: REGLAGES, isLoading: false }),
  useEnregistrerReglagesAgendas: () => ({ mutate: enregistrer, isPending: false }),
  useDeduireLesSalles: () => ({ refetch: refetchDeduction, isFetching: false }),
}));

async function afficher() {
  const { CalendrierSallesSection } = await import('../CalendrierSallesSection');
  renderWithProviders(<CalendrierSallesSection />);
}

beforeEach(() => {
  enregistrer.mockReset();
  refetchDeduction.mockReset().mockResolvedValue({ data: DEDUCTION });
});

describe('Salles de l’emploi du temps', () => {
  it('liste tous les agendas, réglés ou non', async () => {
    await afficher();
    expect(screen.getByText(/Coran - enfants 1/)).toBeInTheDocument();
    expect(screen.getByText(/SI - Adorations/)).toBeInTheDocument();
  });

  it('avertit quand des agendas n’ont pas de salle', async () => {
    await afficher();
    // Sans ce signal, la grille entasse tout en Maziri et l'écran paraît
    // cassé sans qu'on sache pourquoi.
    expect(screen.getByText(/2 agenda\(s\) sur 2 n'ont pas de salle/)).toBeInTheDocument();
  });

  it('n’envoie que les lignes modifiées, en un seul enregistrement', async () => {
    const user = userEvent.setup();
    await afficher();

    await user.selectOptions(screen.getByLabelText(/Salle de Coran/), 'nafi');
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }));

    expect(enregistrer).toHaveBeenCalledTimes(1);
    expect(enregistrer.mock.calls[0][0]).toEqual({
      'coran@g': { salle: 'nafi', nom_court: null, categorie: null, sous_categorie: null },
    });
  });

  it('le nom court saisi part tel quel, et vide revient au calcul', async () => {
    const user = userEvent.setup();
    await afficher();

    const champ = screen.getByLabelText(/Nom court de SI - Adorations/);
    // Le placeholder montre ce que la règle calculerait : vider le champ est
    // alors un geste lisible, pas un saut dans le vide.
    expect(champ).toHaveAttribute('placeholder', 'SI Adorations');

    await user.type(champ, 'SI Ador.');
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }));

    expect(enregistrer.mock.calls[0][0]).toEqual({
      'si@g': { salle: null, nom_court: 'SI Ador.', categorie: null, sous_categorie: null },
    });
  });

  it('« Proposer d’après Google » remplit le formulaire sans rien enregistrer', async () => {
    const user = userEvent.setup();
    await afficher();

    await user.click(screen.getByRole('button', { name: /Proposer d'après Google/ }));

    await waitFor(() =>
      expect(screen.getByLabelText(/Salle de SI - Adorations/)).toHaveValue('maziri'),
    );
    // Le point du test : la proposition ne décide pas à la place d'une personne.
    expect(enregistrer).not.toHaveBeenCalled();
  });

  it('rien n’est envoyé tant que rien n’a été touché', async () => {
    await afficher();
    expect(screen.getByRole('button', { name: /Enregistrer/ })).toBeDisabled();
  });

  it('une catégorie corrigée part avec le lot', async () => {
    const user = userEvent.setup();
    await afficher();
    const champ = screen.getByLabelText(/^Catégorie de SI - Adorations/);
    // La valeur calculée est montrée : vider le champ y revient.
    expect(champ).toHaveAttribute('placeholder', 'Sciences islamiques');
    await user.type(champ, 'Événements');
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }));
    expect(enregistrer.mock.calls[0][0]['si@g']).toMatchObject({ categorie: 'Événements' });
  });
});
