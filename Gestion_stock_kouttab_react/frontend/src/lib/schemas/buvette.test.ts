import { describe, expect, it } from 'vitest';
import {
  adjustBuvetteProductSchema,
  categorieVersOnglet,
  ongletVersCategorie,
} from './buvette';

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

  it('l’ajustement refuse un onglet inconnu', () => {
    const base = { quantity: 3, seuil_alerte: 1, emoji: '☕' };
    expect(adjustBuvetteProductSchema.safeParse({ ...base, onglet_caisse: 'cafe' }).success).toBe(
      true,
    );
    expect(
      adjustBuvetteProductSchema.safeParse({ ...base, onglet_caisse: 'alcool' }).success,
    ).toBe(false);
  });
});
