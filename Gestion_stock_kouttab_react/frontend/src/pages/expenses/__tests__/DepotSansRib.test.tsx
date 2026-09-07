import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/test-utils';
import type { User } from '@/types/api';

/**
 * Déposer une note de frais sans avoir déposé son RIB.
 *
 * La comptabilité rembourse par virement : sans RIB, elle ne peut pas payer et
 * réclamait les coordonnées par messages privés. Le refus vient du backend ; ce
 * qui se joue ici est l'inverse — que le bénévole soit prévenu **avant** d'avoir
 * tout saisi, et qu'aller déposer son RIB ne lui fasse rien perdre.
 */

const creerNote = vi.fn();
let profil: Partial<User> = { id: 7, rib_document_nom: null };

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ can: () => false, user: { id: 7, role: 'Benevole' } }),
}));
vi.mock('@/api/endpoints/auth', () => ({
  useProfile: () => ({ data: profil, isLoading: false }),
  useUpdateProfile: () => ({ mutate: vi.fn(), isPending: false }),
  useUploadRibDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteRibDocument: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock('@/api/endpoints/expenses', () => ({
  useCreateExpense: () => ({ mutate: creerNote, isPending: false }),
  useMyExpenses: () => ({ data: [], isLoading: false }),
  useUpdateExpense: () => ({ mutate: vi.fn(), isPending: false }),
  useAjouterJustificatif: () => ({ mutate: vi.fn(), isPending: false }),
  useMarquerNotesLues: () => ({ mutate: vi.fn(), isPending: false }),
  expenseQueryKeys: { all: ['expenses'] },
}));
vi.mock('@/api/endpoints/notifications', () => ({
  usePendingSummary: () => ({ data: undefined }),
}));
vi.mock('@/api/endpoints/reimbursements', () => ({
  useRemboursementParNote: () => new Map(),
  useMesRemboursements: () => ({ data: [], isLoading: false }),
  reimbursementDocumentPath: (id: number) => `/reimbursements/${id}/document`,
  reimbursementQueryKeys: { all: ['reimbursements'] },
}));
vi.mock('@/api/endpoints/referentials', () => ({
  usePoles: () => ({
    data: [
      { id: 1, nom: 'Frais généraux', is_active: true, requiert_evenement: false, ordre: 1 },
    ],
  }),
  useEvents: () => ({ data: [] }),
  useExpenseCategories: () => ({ data: [{ id: 1, nom: 'Courses', is_active: true, ordre: 1 }] }),
}));

import { MyExpensesPage } from '../MyExpensesPage';

describe('pages/expenses — dépôt sans RIB', () => {
  beforeEach(() => {
    creerNote.mockClear();
    localStorage.clear();
    profil = { id: 7, rib_document_nom: null };
  });

  it('prévient dès l’ouverture du formulaire, avant toute saisie', () => {
    renderWithProviders(<MyExpensesPage />);

    expect(screen.getByTestId('rib-requis')).toBeInTheDocument();
  });

  it('ne prévient plus une fois le RIB déposé ET l’IBAN saisi', () => {
    profil = {
      id: 7,
      rib: 'FR7630001007941234567890185',
      rib_document_nom: 'rib.pdf',
      rib_document_type: 'application/pdf',
    };
    renderWithProviders(<MyExpensesPage />);

    expect(screen.queryByTestId('rib-requis')).not.toBeInTheDocument();
  });

  it('prévient quand le document est là mais l’IBAN manque', () => {
    // Le cas qui passait : le contrôle ne regardait que le document. La note
    // partait, et l'écran comptable l'affichait sous « RIB non renseigné » —
    // en masquant jusqu'au bouton de téléchargement de la pièce déposée.
    profil = { id: 7, rib_document_nom: 'rib.pdf', rib_document_type: 'application/pdf' };
    renderWithProviders(<MyExpensesPage />);

    const encart = screen.getByTestId('rib-requis');
    expect(encart).toBeInTheDocument();
    // Et il dit ce qui manque : réclamer « déposez votre RIB » à quelqu'un qui
    // l'a déjà déposé le fait redéposer la même photo en boucle.
    expect(encart).toHaveTextContent(/IBAN/i);
  });

  it('prévient aussi quand le RIB déposé n’est pas un PDF', () => {
    // Cas résiduel : document illisible que la migration n'a pas su convertir.
    // Le nom seul ne prouve rien — l'API, elle, exige le format.
    profil = { id: 7, rib_document_nom: 'rib.png', rib_document_type: 'image/png' };
    renderWithProviders(<MyExpensesPage />);

    expect(screen.getByTestId('rib-requis')).toBeInTheDocument();
  });

  it('refuse l’envoi sans appeler l’API', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MyExpensesPage />);

    await user.type(screen.getByLabelText(/Fournisseur/), 'Carrefour');
    await user.click(screen.getByRole('button', { name: /Soumettre la demande/i }));

    await waitFor(() => expect(screen.getByTestId('rib-requis')).toBeInTheDocument());
    expect(creerNote).not.toHaveBeenCalled();
  });

  it('mène au profil et garde la saisie au retour', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MyExpensesPage />);

    await user.type(screen.getByLabelText(/Fournisseur/), 'Carrefour');
    await user.click(within(screen.getByTestId('rib-requis')).getByRole('button'));

    // On est bien sur le profil : le dépôt du RIB s'y trouve.
    expect(await screen.findByTestId('rib-document-input')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /Soumettre une note/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/Fournisseur/)).toHaveValue('Carrefour'),
    );
  });
});

/**
 * Déposer une note de frais sans y joindre le moindre ticket.
 *
 * Elle partait : `files` est facultatif côté API, et rien ne l'exigeait ici non
 * plus. Le comptable recevait un courriel annonçant la dépense, mais jamais les
 * pièces — l'envoi comptable ne part que s'il y en a. Il lui restait à réclamer
 * lui-même une preuve que le bénévole croyait avoir fournie.
 */
describe('pages/expenses — dépôt sans justificatif', () => {
  beforeEach(() => {
    creerNote.mockClear();
    localStorage.clear();
    // Compte complet : c'est le justificatif, et lui seul, qui doit manquer.
    profil = {
      id: 7,
      rib: 'FR7630001007941234567890185',
      rib_document_nom: 'rib.pdf',
      rib_document_type: 'application/pdf',
    };
  });

  it('refuse l’envoi sans appeler l’API', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MyExpensesPage />);

    await user.type(screen.getByLabelText(/Fournisseur/), 'Carrefour');
    await user.click(screen.getByRole('button', { name: /Soumettre la demande/i }));

    await waitFor(() => expect(screen.getByTestId('ticket-requis')).toBeInTheDocument());
    expect(creerNote).not.toHaveBeenCalled();
  });
});
