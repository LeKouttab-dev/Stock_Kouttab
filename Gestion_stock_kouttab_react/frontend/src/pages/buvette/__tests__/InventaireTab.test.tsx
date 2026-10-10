import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import {
  fireEvent,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from '@/test/test-utils';
import type { Inventaire, InventaireEspeces, InventaireLigne } from '@/types/api';
import { InventaireTab } from '../tabs/InventaireTab';
import { BASE_URL, connecter } from './helpers';

function ligne(
  partiel: Partial<InventaireLigne> & Pick<InventaireLigne, 'id' | 'nom'>,
): InventaireLigne {
  return {
    product_id: partiel.id,
    categorie: 'boissons',
    emoji: '🥤',
    image_url: null,
    prix_cents: 100,
    stock_actuel: 0,
    quantite_comptee: 0,
    quantite_theorique: null,
    ecart: null,
    valeur_ecart_cents: null,
    ...partiel,
  };
}

const RESUME_VIDE = {
  nb_produits: 2,
  nb_ecarts: 0,
  ecart_unites: 0,
  valeur_ecart_cents: 0,
  perte_cents: 0,
};

function inventaire(partiel: Partial<Inventaire> = {}): Inventaire {
  return {
    id: 12,
    statut: 'en_cours',
    debut_le: '2026-10-09T18:00:00Z',
    stock_valide_le: null,
    termine_le: null,
    cree_par: 'Omar',
    periode_especes_debut: null,
    periode_especes_fin: null,
    especes_attendues_cents: null,
    especes_comptees_cents: null,
    ecart_especes_cents: null,
    nb_ventes_especes: null,
    commentaire: null,
    lignes: [
      ligne({ id: 1, nom: 'Coca', prix_cents: 150, stock_actuel: 5 }),
      ligne({ id: 2, nom: 'Chips', categorie: 'sucre_sale', emoji: '🥔', stock_actuel: 3 }),
    ],
    resume: RESUME_VIDE,
    ...partiel,
  };
}

/** Un inventaire non terminé, servi à la fois par /en-cours et /12. */
function enCours(inv: Inventaire) {
  server.use(
    http.get(`${BASE_URL}/buvette/inventaires/en-cours`, () =>
      HttpResponse.json({ inventaire: inv }),
    ),
    http.get(`${BASE_URL}/buvette/inventaires/12`, () => HttpResponse.json(inv)),
  );
}

const ESPECES: InventaireEspeces = {
  periode_debut: '2026-10-01T20:00:00Z',
  periode_fin: '2026-10-09T18:30:00Z',
  premier_inventaire: false,
  attendu_cents: 4250,
  nb_ventes: 2,
  ventes: [
    {
      cle: 'v1',
      sold_at: '2026-10-05T17:00:00Z',
      total_cents: 3000,
      articles: [{ nom: 'Coca', quantite: 2, montant_cents: 3000 }],
    },
    {
      cle: 'v2',
      sold_at: '2026-10-06T17:00:00Z',
      total_cents: 1250,
      articles: [{ nom: 'Chips', quantite: 1, montant_cents: 1250 }],
    },
  ],
};

async function ouvrir(role: 'AdminStock' | 'Compta' = 'AdminStock') {
  renderWithProviders(<InventaireTab />);
  connecter(role);
}

describe('pages/buvette/tabs/InventaireTab', () => {
  it('démarre un inventaire et ouvre le comptage', async () => {
    let cree = false;
    server.use(
      http.post(`${BASE_URL}/buvette/inventaires`, () => {
        cree = true;
        return HttpResponse.json(inventaire(), { status: 201 });
      }),
      http.get(`${BASE_URL}/buvette/inventaires/12`, () => HttpResponse.json(inventaire())),
    );
    const user = userEvent.setup();
    await ouvrir();

    await user.click(await screen.findByRole('button', { name: /Démarrer un nouvel inventaire/ }));
    expect(cree).toBe(true);
    expect(await screen.findByLabelText('Quantité comptée : Coca')).toHaveValue('0');
    expect(screen.getByText(/Stock en base : 5/)).toBeInTheDocument();
    const etapes = screen.getByRole('list', { name: 'Étapes de l’inventaire' });
    expect(within(etapes).getByText('Stock').closest('li')).toHaveAttribute('aria-current', 'step');
  });

  it('compteur : + et −, jamais sous 0, saisie directe, brouillon enregistré', async () => {
    enCours(inventaire());
    const envois: { id: number; quantite_comptee: number }[][] = [];
    server.use(
      http.put(`${BASE_URL}/buvette/inventaires/12/lignes`, async ({ request }) => {
        const corps = (await request.json()) as {
          lignes: { id: number; quantite_comptee: number }[];
        };
        envois.push(corps.lignes);
        return HttpResponse.json(inventaire());
      }),
    );
    const user = userEvent.setup();
    await ouvrir();
    await user.click(
      await screen.findByRole('button', { name: /Reprendre l’inventaire en cours/ }),
    );

    const coca = await screen.findByLabelText('Quantité comptée : Coca');
    const plusCoca = screen.getByRole('button', { name: 'Ajouter un Coca' });
    const moinsCoca = screen.getByRole('button', { name: 'Retirer un Coca' });
    expect(moinsCoca).toBeDisabled();

    await user.click(plusCoca);
    await user.click(plusCoca);
    await user.click(plusCoca);
    expect(coca).toHaveValue('3');
    await user.click(moinsCoca);
    expect(coca).toHaveValue('2');

    const chips = screen.getByLabelText('Quantité comptée : Chips');
    expect(screen.getByRole('button', { name: 'Retirer un Chips' })).toBeDisabled();
    fireEvent.change(chips, { target: { value: '-7' } });
    expect(chips).toHaveValue('7');
    fireEvent.change(chips, { target: { value: '12' } });
    expect(chips).toHaveValue('12');

    expect(await screen.findByText('Enregistré', {}, { timeout: 3000 })).toBeInTheDocument();
    expect(envois).toHaveLength(1);
    expect(envois[0]).toEqual(
      expect.arrayContaining([
        { id: 1, quantite_comptee: 2 },
        { id: 2, quantite_comptee: 12 },
      ]),
    );
  });

  it('récapitule les écarts puis valide le stock après confirmation', async () => {
    enCours(inventaire());
    const ordre: string[] = [];
    server.use(
      http.put(`${BASE_URL}/buvette/inventaires/12/lignes`, () => {
        ordre.push('put');
        return HttpResponse.json(inventaire());
      }),
      http.post(`${BASE_URL}/buvette/inventaires/12/valider-stock`, () => {
        ordre.push('valider');
        return HttpResponse.json(inventaire({ statut: 'stock_valide' }));
      }),
      http.get(`${BASE_URL}/buvette/inventaires/12/especes`, () => HttpResponse.json(ESPECES)),
    );
    const user = userEvent.setup();
    await ouvrir();
    await user.click(await screen.findByRole('button', { name: /Reprendre/ }));

    // Coca : 4 comptés pour 5 en base ; Chips : 3 pour 3.
    const plusCoca = await screen.findByRole('button', { name: 'Ajouter un Coca' });
    for (let i = 0; i < 4; i++) await user.click(plusCoca);
    fireEvent.change(screen.getByLabelText('Quantité comptée : Chips'), {
      target: { value: '3' },
    });

    await user.click(screen.getByRole('button', { name: 'Voir les écarts' }));
    const ligneCoca = await screen.findByTestId('recap-1');
    expect(within(ligneCoca).getByText('−1')).toBeInTheDocument();
    expect(within(ligneCoca).getByText('−1,50 €')).toBeInTheDocument();
    expect(screen.queryByTestId('recap-2')).not.toBeInTheDocument();
    expect(screen.getByTestId('recap-perte')).toHaveTextContent('1.50 €');
    expect(ordre).toEqual(['put']);

    await user.click(screen.getByRole('button', { name: /Valider le stock/ }));
    const dialogue = await screen.findByRole('dialog');
    expect(
      within(dialogue).getByText(
        'Le stock de chaque produit sera remplacé par la quantité comptée.',
      ),
    ).toBeInTheDocument();
    expect(ordre).toEqual(['put']);

    await user.click(within(dialogue).getByRole('button', { name: 'Remplacer le stock' }));
    await waitFor(() => expect(ordre).toEqual(['put', 'valider']));
    // Étape 2 : les espèces.
    expect(await screen.findByTestId('especes-attendues')).toHaveTextContent('42.50 €');
  });

  it('abandonne le brouillon après confirmation', async () => {
    enCours(inventaire());
    let supprime = false;
    server.use(
      http.delete(`${BASE_URL}/buvette/inventaires/12`, () => {
        supprime = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    await ouvrir();
    await user.click(await screen.findByRole('button', { name: /Reprendre/ }));
    await user.click(await screen.findByRole('button', { name: 'Abandonner' }));
    const dialogue = await screen.findByRole('dialog');
    expect(supprime).toBe(false);
    await user.click(within(dialogue).getByRole('button', { name: 'Abandonner l’inventaire' }));
    await waitFor(() => expect(supprime).toBe(true));
  });

  it('écart espèces : manque, surplus, compte juste, puis termine', async () => {
    enCours(inventaire({ statut: 'stock_valide' }));
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/inventaires/12/especes`, () => HttpResponse.json(ESPECES)),
      http.post(`${BASE_URL}/buvette/inventaires/12/terminer`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          inventaire({
            statut: 'termine',
            termine_le: '2026-10-09T19:00:00Z',
            especes_attendues_cents: 4250,
            especes_comptees_cents: 4500,
            ecart_especes_cents: 250,
          }),
        );
      }),
    );
    const user = userEvent.setup();
    await ouvrir();
    await user.click(await screen.findByRole('button', { name: /Reprendre/ }));

    expect(await screen.findByTestId('especes-attendues')).toHaveTextContent('42.50 €');
    expect(screen.getByText('2 × Coca')).toBeInTheDocument();
    // 17:00 UTC = 19:00 à Paris.
    expect(screen.getByText('05/10/2026 19:00')).toBeInTheDocument();
    const champ = screen.getByLabelText('Espèces comptées dans la boîte (€)');

    await user.type(champ, '40');
    let ecart = screen.getByTestId('ecart-especes');
    expect(ecart).toHaveTextContent('Manque 2,50 €');
    expect(ecart).toHaveAttribute('data-ton', 'leger');

    await user.clear(champ);
    await user.type(champ, '42,50');
    ecart = screen.getByTestId('ecart-especes');
    expect(ecart).toHaveTextContent('Compte juste');
    expect(ecart).toHaveClass('text-sage-700');

    await user.clear(champ);
    await user.type(champ, '45');
    expect(screen.getByTestId('ecart-especes')).toHaveTextContent('Surplus de 2,50 €');

    await user.type(screen.getByLabelText('Commentaire (facultatif)'), 'Pièce trouvée');
    await user.click(screen.getByRole('button', { name: /Terminer l’inventaire/ }));
    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps).toEqual({
      especes_comptees_cents: 4500,
      commentaire: 'Pièce trouvée',
      debut: null,
    });
    // Étape 3 : le rapport.
    expect(await screen.findByTestId('rapport-ecart-especes')).toHaveTextContent(
      'Surplus de 2,50 €',
    );
  });

  it('étape espèces : la période part de la dernière clôture de caisse', async () => {
    enCours(inventaire({ statut: 'stock_valide' }));
    server.use(
      http.get(`${BASE_URL}/buvette/inventaires/12/especes`, () =>
        HttpResponse.json({
          ...ESPECES,
          dernier_comptage: { type: 'cloture', le: '2026-10-01T20:00:00Z' },
        }),
      ),
    );
    const user = userEvent.setup();
    await ouvrir();
    await user.click(await screen.findByRole('button', { name: /Reprendre/ }));

    expect(
      await screen.findByText(/2 vente\(s\) en espèces, depuis la clôture du 01\/10\/2026 22:00/),
    ).toBeInTheDocument();
  });

  it('premier inventaire : la date de début est obligatoire et envoyée', async () => {
    enCours(inventaire({ statut: 'stock_valide' }));
    const debuts: (string | null)[] = [];
    let corps: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE_URL}/buvette/inventaires/12/especes`, ({ request }) => {
        const debut = new URL(request.url).searchParams.get('debut');
        debuts.push(debut);
        return HttpResponse.json(
          debut
            ? { ...ESPECES, premier_inventaire: true }
            : { ...ESPECES, premier_inventaire: true, attendu_cents: 0, nb_ventes: 0, ventes: [] },
        );
      }),
      http.post(`${BASE_URL}/buvette/inventaires/12/terminer`, async ({ request }) => {
        corps = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(inventaire({ statut: 'termine' }));
      }),
    );
    const user = userEvent.setup();
    await ouvrir();
    await user.click(await screen.findByRole('button', { name: /Reprendre/ }));

    const date = await screen.findByLabelText('Ventes en espèces depuis le');
    expect(screen.queryByLabelText('Espèces comptées dans la boîte (€)')).not.toBeInTheDocument();
    fireEvent.change(date, { target: { value: '2026-09-01' } });

    expect(await screen.findByTestId('especes-attendues')).toHaveTextContent('42.50 €');
    expect(debuts).toContain('2026-09-01');
    await user.type(screen.getByLabelText('Espèces comptées dans la boîte (€)'), '42,5');
    await user.click(screen.getByRole('button', { name: /Terminer l’inventaire/ }));
    await waitFor(() => expect(corps).not.toBeNull());
    expect(corps).toMatchObject({ especes_comptees_cents: 4250, debut: '2026-09-01' });
  });

  describe('historique et exports', () => {
    const clic = vi.fn();
    let noms: string[] = [];
    beforeEach(() => {
      window.URL.createObjectURL = vi.fn(() => 'blob:fichier');
      window.URL.revokeObjectURL = vi.fn();
      noms = [];
      vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
        this: HTMLAnchorElement,
      ) {
        noms.push(this.download);
        clic();
      });
    });
    afterEach(() => {
      vi.restoreAllMocks();
      clic.mockReset();
    });

    const termine = inventaire({
      statut: 'termine',
      termine_le: '2026-10-08T19:00:00Z',
      especes_attendues_cents: 4250,
      especes_comptees_cents: 4000,
      ecart_especes_cents: -250,
      lignes: [
        ligne({
          id: 1,
          nom: 'Coca',
          prix_cents: 150,
          stock_actuel: 4,
          quantite_comptee: 4,
          quantite_theorique: 5,
          ecart: -1,
          valeur_ecart_cents: -150,
        }),
      ],
      resume: {
        ...RESUME_VIDE,
        nb_ecarts: 1,
        ecart_unites: -1,
        valeur_ecart_cents: -150,
        perte_cents: 150,
        achats_cents: 4200,
      },
    });

    it('filtre l’historique, ouvre un rapport et exporte', async () => {
      let paramsHistorique: URLSearchParams | null = null;
      let paramsExport: URLSearchParams | null = null;
      let exportRapport = false;
      const resume: Record<string, unknown> = { ...termine };
      delete resume.lignes;
      server.use(
        http.get(`${BASE_URL}/buvette/inventaires`, ({ request }) => {
          paramsHistorique = new URL(request.url).searchParams;
          return HttpResponse.json([resume]);
        }),
        http.get(`${BASE_URL}/buvette/inventaires/12`, () => HttpResponse.json(termine)),
        http.get(`${BASE_URL}/buvette/inventaires/export.xlsx`, ({ request }) => {
          paramsExport = new URL(request.url).searchParams;
          return new HttpResponse(new Blob(['xlsx']), {
            headers: {
              'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            },
          });
        }),
        http.get(`${BASE_URL}/buvette/inventaires/12/export.xlsx`, () => {
          exportRapport = true;
          return new HttpResponse(new Blob(['xlsx']), {
            headers: {
              'Content-Disposition': 'attachment; filename="inventaire-12-2026-10-08.xlsx"',
            },
          });
        }),
      );
      const user = userEvent.setup();
      await ouvrir('Compta');

      fireEvent.click(screen.getByRole('button', { name: 'Personnalisé' }));

      fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-10-01' } });
      fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-10-31' } });
      await waitFor(() => expect(paramsHistorique?.get('fin')).toBe('2026-10-31'));
      expect(paramsHistorique!.get('debut')).toBe('2026-10-01');

      await user.click(screen.getByRole('button', { name: /Exporter l’historique/ }));
      await waitFor(() => expect(clic).toHaveBeenCalledTimes(1));
      expect(paramsExport!.get('debut')).toBe('2026-10-01');
      expect(paramsExport!.get('fin')).toBe('2026-10-31');

      await user.click(
        await screen.findByRole('button', { name: 'Ouvrir l’inventaire du 09/10/2026' }),
      );
      expect(await screen.findByTestId('rapport-perte')).toHaveTextContent('1.50 €');
      expect(screen.getByTestId('rapport-ecart-especes')).toHaveTextContent('Manque 2,50 €');
      // Achats de la période : total des réappros entre les deux inventaires.
      expect(screen.getByText('Achats de la période')).toBeInTheDocument();
      expect(screen.getByTestId('rapport-achats')).toHaveTextContent('42.00 €');

      await user.click(screen.getByRole('button', { name: 'Exporter (Excel)' }));
      await waitFor(() => expect(clic).toHaveBeenCalledTimes(2));
      expect(exportRapport).toBe(true);
      expect(noms[1]).toBe('inventaire-12-2026-10-08.xlsx');
    });

    it('lecture seule : ni démarrer, ni reprendre, ni compter', async () => {
      await ouvrir('Compta');
      expect(await screen.findByText('Aucun inventaire en cours.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Démarrer/ })).not.toBeInTheDocument();
    });

    it('lecture seule : un inventaire en cours ne se reprend pas', async () => {
      enCours(inventaire());
      await ouvrir('Compta');
      expect(await screen.findByText(/Un inventaire est en cours depuis le/)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Reprendre/ })).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Quantité comptée : Coca')).not.toBeInTheDocument();
    });
  });
});
