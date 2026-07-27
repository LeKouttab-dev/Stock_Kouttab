import { describe, expect, it } from 'vitest';

import { centsToEuros, eurosToCents, expenseTotal } from './money';

describe('lib/money', () => {
  describe('expenseTotal', () => {
    it('soustrait le déjà-remboursé et la remise', () => {
      expect(
        expenseTotal({ montant: 100, remboursement_deja_emis: 30, remise: 10 }),
      ).toBe(60);
    });

    it('tolère les champs absents', () => {
      expect(expenseTotal({ montant: 42 })).toBe(42);
      expect(expenseTotal({ montant: 42, remboursement_deja_emis: null, remise: null })).toBe(
        42,
      );
    });

    it('accepte les montants transmis en chaîne par l’API', () => {
      expect(
        expenseTotal({ montant: '100.50', remboursement_deja_emis: '0.50', remise: '0' }),
      ).toBe(100);
    });

    it('ne descend jamais sous zéro', () => {
      // Un total négatif s'afficherait comme une dette du bénévole.
      expect(expenseTotal({ montant: 10, remboursement_deja_emis: 30 })).toBe(0);
    });
  });

  describe('eurosToCents', () => {
    it('corrige les erreurs de virgule flottante sur 2 décimales', () => {
      // 19.99 * 100 vaut 1998.9999999999998 : une troncature donnerait 1998.
      expect(eurosToCents(19.99)).toBe(1999);
      expect(eurosToCents(0.1)).toBe(10);
      expect(eurosToCents(0.07)).toBe(7);
      expect(eurosToCents(123.45)).toBe(12345);
    });

    it('arrondit au centime inférieur au-delà de 2 décimales', () => {
      // Limite connue et sans effet ici : les prix de buvette ont deux
      // décimales. 1.005 vaut 1.00499999999999989 en binaire, l'arrondi donne
      // donc 100 et non 101 — comportement de Math.round, pas un défaut du
      // module. Documenté pour éviter qu'un futur lecteur le « corrige ».
      expect(eurosToCents(1.005)).toBe(100);
    });

    it('accepte une chaîne', () => {
      expect(eurosToCents('2.50')).toBe(250);
    });

    it('retourne 0 pour une valeur inexploitable', () => {
      expect(eurosToCents('abc')).toBe(0);
      expect(eurosToCents(NaN)).toBe(0);
    });
  });

  describe('centsToEuros', () => {
    it('fait l’aller-retour', () => {
      expect(centsToEuros(eurosToCents(19.99))).toBe(19.99);
    });

    it('retourne 0 pour null ou undefined', () => {
      expect(centsToEuros(null)).toBe(0);
      expect(centsToEuros(undefined)).toBe(0);
    });
  });
});
