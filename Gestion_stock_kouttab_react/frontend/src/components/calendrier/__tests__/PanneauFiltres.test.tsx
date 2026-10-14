import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PanneauFiltres } from '../PanneauFiltres';
import type { Agenda } from '@/types/api';

/**
 * Le filtre en arbre : par matière, puis par public, puis les agendas.
 * Quarante-cinq cases à plat étaient inutilisables.
 */

function agenda(id: string, categorie: string, sous: string | null, rang: number): Agenda {
  return {
    id,
    nom: `${id} 2026/2027`,
    nom_court: id,
    restreint: false,
    categorie,
    sous_categorie: sous,
    categorie_rang: rang,
  };
}

const AGENDAS = [
  agenda('Coran ENF 1', 'Coran', 'Coran enfants', 0),
  agenda('Coran ENF 2', 'Coran', 'Coran enfants', 0),
  agenda('Coran F N 2', 'Coran', 'Coran femmes', 0),
  agenda('SI Adorations', 'Sciences islamiques', null, 1),
  agenda('Non classé', 'Autres', null, 9),
];

const regler = vi.fn();

function afficher(masques: string[] = [], recherche = '') {
  return render(
    <PanneauFiltres
      agendas={AGENDAS}
      chargement={false}
      recherche={recherche}
      masques={masques}
      salles={{}}
      sallesMasquees={[]}
      parSalle={false}
      onRecherche={() => {}}
      onReglerAgendas={regler}
      onBasculerSalle={() => {}}
    />,
  );
}

beforeEach(() => {
  regler.mockReset();
  localStorage.clear();
});

describe('PanneauFiltres', () => {
  it('montre les catégories dans l’ordre servi, toutes repliées', () => {
    afficher();
    const arbre = screen.getByRole('list', { name: /Agendas par catégorie/ });
    const libelles = within(arbre)
      .getAllByRole('button', { name: /^Déplier/ })
      .map((b) => b.getAttribute('aria-label'));
    expect(libelles).toEqual(['Déplier Coran', 'Déplier Sciences islamiques', 'Déplier Autres']);
    // Repliées : aucun agenda visible.
    expect(screen.queryByText('Coran ENF 1')).toBeNull();
  });

  it('déplier une catégorie montre ses sous-catégories, puis ses agendas', async () => {
    const user = userEvent.setup();
    afficher();
    await user.click(screen.getByRole('button', { name: 'Déplier Coran' }));
    expect(screen.getByRole('button', { name: 'Déplier Coran enfants' })).toBeInTheDocument();
    expect(screen.queryByText('Coran ENF 1')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Déplier Coran enfants' }));
    expect(screen.getByText('Coran ENF 1')).toBeInTheDocument();
  });

  it('la case d’une catégorie masque tous ses agendas d’un coup', async () => {
    const user = userEvent.setup();
    afficher();
    await user.click(screen.getByRole('checkbox', { name: 'Afficher Coran' }));
    expect(regler).toHaveBeenCalledWith(['Coran ENF 1', 'Coran ENF 2', 'Coran F N 2'], false);
  });

  it('une catégorie dont une partie est masquée est « partielle », et se complète au clic', async () => {
    const user = userEvent.setup();
    afficher(['Coran ENF 2']);
    const caseCoran = screen.getByRole('checkbox', { name: 'Afficher Coran' });
    expect(caseCoran).toHaveAttribute('data-state', 'indeterminate');
    await user.click(caseCoran);
    expect(regler).toHaveBeenCalledWith(['Coran ENF 1', 'Coran ENF 2', 'Coran F N 2'], true);
  });

  it('une recherche déplie ce qui contient un résultat', () => {
    afficher([], 'ENF 2');
    expect(screen.getByText('Coran ENF 2')).toBeInTheDocument();
    expect(screen.queryByText('SI Adorations')).toBeNull();
  });

  it('l’état déplié est mémorisé d’une visite à l’autre', async () => {
    const user = userEvent.setup();
    const { unmount } = afficher();
    await user.click(screen.getByRole('button', { name: 'Déplier Coran' }));
    unmount();
    afficher();
    expect(screen.getByRole('button', { name: 'Replier Coran' })).toBeInTheDocument();
  });
});
