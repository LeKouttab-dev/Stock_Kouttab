import { describe, expect, it } from 'vitest';
import { modifierBuvetteProductSchema, categorieVersOnglet, ongletVersCategorie } from './buvette';

describe('onglet de la tablette de caisse', () => {
  it('« Pas sur la tablette » part au serveur comme null, et non comme une chaîne', () => {
    // Le serveur refuserait « aucun » (422) : le produit ne se retirerait jamais
    // de la tablette.
    expect(ongletVersCategorie('aucun')).toBeNull();
    expect(ongletVersCategorie('cafe')).toBe('cafe');
  });

  it('un produit sans catégorie s’affiche « Pas sur la tablette »', () => {
    // Les produits antérieurs à la caisse n'ont pas le champ : ni undefined ni
    // null ne doivent laisser la liste déroulante vide.
    expect(categorieVersOnglet(null)).toBe('aucun');
    expect(categorieVersOnglet(undefined)).toBe('aucun');
    expect(categorieVersOnglet('boissons')).toBe('boissons');
  });

  it('la fiche refuse un onglet inconnu', () => {
    // La fiche porte le nom et le prix depuis que la tablette a remplacé la
    // boutique HelloAsso : ils ne se corrigeaient qu'en recréant le produit.
    const base = { name: 'Café', price_euros: 1.5, seuil_alerte: 1, emoji: '☕' };
    expect(modifierBuvetteProductSchema.safeParse({ ...base, onglet_caisse: 'cafe' }).success).toBe(
      true,
    );
    expect(
      modifierBuvetteProductSchema.safeParse({ ...base, onglet_caisse: 'alcool' }).success,
    ).toBe(false);
  });

  it('la fiche exige un nom et un prix', () => {
    const base = { seuil_alerte: 1, emoji: '☕', onglet_caisse: 'cafe' };
    expect(
      modifierBuvetteProductSchema.safeParse({ ...base, name: '', price_euros: 1.5 }).success,
    ).toBe(false);
    // Un prix négatif n'existe pas en caisse : ce serait un encaissement à l'envers.
    expect(
      modifierBuvetteProductSchema.safeParse({ ...base, name: 'Café', price_euros: -1 }).success,
    ).toBe(false);
    // La gratuité, elle, est légitime (verre d'eau, dégustation).
    expect(
      modifierBuvetteProductSchema.safeParse({ ...base, name: 'Eau', price_euros: 0 }).success,
    ).toBe(true);
  });

  it('la fiche ne porte plus de quantité : le stock ne part pas au serveur', () => {
    const r = modifierBuvetteProductSchema.safeParse({
      name: 'Café',
      price_euros: 1.5,
      quantity: 99,
      seuil_alerte: 1,
      emoji: '☕',
      onglet_caisse: 'cafe',
    });
    expect(r.success).toBe(true);
    expect(r.success && 'quantity' in r.data).toBe(false);
  });
});

describe('code-barres de la fiche produit', () => {
  const base = {
    name: 'Café',
    price_euros: 1.5,
    seuil_alerte: 1,
    emoji: '☕',
    onglet_caisse: 'cafe',
  };

  it('accepte un champ vide (sans code-barres) et 8 à 14 chiffres', () => {
    expect(modifierBuvetteProductSchema.safeParse({ ...base, barcode: '' }).success).toBe(true);
    expect(modifierBuvetteProductSchema.safeParse({ ...base, barcode: ' 3017620422003 ' })).toEqual(
      expect.objectContaining({
        success: true,
        data: expect.objectContaining({ barcode: '3017620422003' }),
      }),
    );
  });

  it('refuse un code trop court ou non numérique, comme le serveur', () => {
    expect(modifierBuvetteProductSchema.safeParse({ ...base, barcode: '1234' }).success).toBe(
      false,
    );
    expect(modifierBuvetteProductSchema.safeParse({ ...base, barcode: 'abcdefgh' }).success).toBe(
      false,
    );
  });
});
