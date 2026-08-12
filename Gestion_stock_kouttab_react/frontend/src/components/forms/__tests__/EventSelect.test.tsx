import { useState } from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { AppEvent } from '@/types/api';

/**
 * Saisir un événement absent du référentiel.
 *
 * Ce cas était **bloqué en production** : l'affichage du champ libre se
 * déduisait du texte déjà saisi, si bien que choisir « Mon événement n'est pas
 * dans la liste » ne faisait rien apparaître. Le formulaire réclamait alors un
 * événement qu'aucun champ ne permettait d'entrer, et le dépôt s'arrêtait là.
 */

const evenements: AppEvent[] = [
  {
    id: 1,
    nom: 'Gala de printemps',
    date_evenement: '2026-04-12',
    source: 'helloasso',
    is_active: true,
    type_ev: 'T',
  } as AppEvent,
  {
    id: 2,
    nom: 'Sortie familles',
    date_evenement: null,
    source: 'manuel',
    is_active: true,
    type_ev: 'G',
  } as AppEvent,
];

const etatRequete = { data: evenements, isLoading: false, isError: false };

vi.mock('@/api/endpoints/referentials', () => ({
  useEvents: () => etatRequete,
}));

import { EventSelect } from '../EventSelect';

/** Composant hôte minimal : le sélecteur est piloté par son parent. */
function Formulaire({ typeEvenement }: { typeEvenement?: string | null }) {
  const [eventId, setEventId] = useState<number | null>(null);
  const [freeText, setFreeText] = useState('');
  return (
    <div>
      <EventSelect
        eventId={eventId}
        freeText={freeText}
        onEventIdChange={setEventId}
        onFreeTextChange={setFreeText}
        typeEvenement={typeEvenement}
      />
      <output data-testid="valeur">
        {eventId !== null ? `id:${eventId}` : `libre:${freeText}`}
      </output>
    </div>
  );
}

describe('components/forms/EventSelect', () => {
  it("ouvre le champ de saisie quand l'événement n'est pas dans la liste", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Formulaire />);

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText("Mon événement n'est pas dans la liste"));

    // C'est tout le bug : ce champ n'apparaissait jamais.
    const champ = await screen.findByPlaceholderText(/Saisissez le nom/i);
    expect(champ).toBeInTheDocument();
  });

  it('remonte le nom saisi au formulaire', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Formulaire />);

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText("Mon événement n'est pas dans la liste"));
    await user.type(await screen.findByPlaceholderText(/Saisissez le nom/i), 'Repas de quartier');

    await waitFor(() =>
      expect(screen.getByTestId('valeur')).toHaveTextContent('libre:Repas de quartier'),
    );
  });

  it("referme le champ libre si l'on choisit finalement un événement listé", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Formulaire />);

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText("Mon événement n'est pas dans la liste"));
    expect(await screen.findByPlaceholderText(/Saisissez le nom/i)).toBeInTheDocument();

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText(/Gala de printemps/));

    await waitFor(() =>
      expect(screen.queryByPlaceholderText(/Saisissez le nom/i)).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId('valeur')).toHaveTextContent('id:1');
  });

  it('ne propose que les événements de la famille du pôle, et les non classés', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Formulaire typeEvenement="T" />);

    await user.click(screen.getByRole('combobox'));

    expect(screen.getByText(/Gala de printemps/)).toBeInTheDocument();
    expect(screen.queryByText(/Sortie familles/)).not.toBeInTheDocument();
  });
});
