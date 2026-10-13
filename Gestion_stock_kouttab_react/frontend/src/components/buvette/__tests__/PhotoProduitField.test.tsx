import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders, screen, userEvent } from '@/test/test-utils';
import type { BuvetteProduct } from '@/types/api';
import { PhotoProduitField } from '../PhotoProduitField';

const EXPRESSO: BuvetteProduct = {
  id: 32,
  helloasso_tier_id: 23362879,
  name: 'Expresso',
  description: null,
  price_cents: 100,
  quantity: 9,
  seuil_alerte: 5,
  emoji: '☕',
  image_url: 'https://cdn.helloasso.com/img/expresso.jpg',
  is_active: true,
  alert_sent: false,
  last_synced_at: null,
  low_stock: false,
  caisse_category: 'cafe',
  barcode: null,
  dernier_prix_achat_cents: null,
};

const PECHE: BuvetteProduct = {
  ...EXPRESSO,
  id: 11,
  name: 'CRISTALINE - PÊCHE',
  image_url: 'https://cdn.helloasso.com/img/peche.jpg',
  caisse_category: 'boissons',
};

const SANS_PHOTO: BuvetteProduct = { ...EXPRESSO, id: 40, name: 'Gaufre', image_url: null };

describe('PhotoProduitField : reprendre la photo d’un produit', () => {
  it('propose les produits ayant une photo et remonte celui choisi', async () => {
    const onSource = vi.fn();
    const onFichier = vi.fn();
    renderWithProviders(
      <PhotoProduitField
        emoji="☕"
        onFichier={onFichier}
        sources={[EXPRESSO, PECHE, SANS_PHOTO]}
        onSource={onSource}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: /Reprendre la photo d’un produit|Reprendre la photo d'un produit/ }));
    expect(screen.queryByText('Gaufre')).not.toBeInTheDocument();

    // Recherche sans accents ni casse.
    await userEvent.type(screen.getByLabelText('Rechercher un produit'), 'peche');
    expect(screen.queryByText('Expresso')).not.toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText('Rechercher un produit'));

    await userEvent.click(screen.getByRole('button', { name: /Expresso/ }));

    expect(onSource).toHaveBeenLastCalledWith(EXPRESSO);
    expect(onFichier).toHaveBeenLastCalledWith(null);
    expect(screen.getByText(/Photo reprise de « Expresso »/)).toBeInTheDocument();
    // L'aperçu montre la photo reprise.
    expect(document.querySelector(`img[src="${EXPRESSO.image_url}"]`)).not.toBeNull();
  });

  it('sans sources, pas de bouton « Reprendre »', () => {
    renderWithProviders(<PhotoProduitField emoji="☕" onFichier={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Reprendre la photo/ })).not.toBeInTheDocument();
  });
});
