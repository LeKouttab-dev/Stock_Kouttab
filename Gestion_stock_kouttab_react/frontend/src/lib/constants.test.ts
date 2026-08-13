import { describe, expect, it } from 'vitest';
import { EXPENSE_STATUS, INVOICE_STATUS, normaliserStatut } from './constants';

/**
 * Les statuts hérités de la version Streamlit s'écrivent **sans accents**.
 *
 * Le formulaire de validation les rejetait à la volée : son schéma n'accepte
 * que les valeurs canoniques, si bien que « Mettre à jour » ne partait jamais,
 * sans le moindre message. Les anciennes notes étaient donc impossibles à
 * corriger, alors que les récentes fonctionnaient — d'où un défaut qui ne se
 * manifestait que sur une partie des lignes.
 */
describe('lib/constants — normaliserStatut', () => {
  it('ramène un statut hérité à son écriture actuelle', () => {
    expect(normaliserStatut('Refusee', EXPENSE_STATUS)).toBe('Refusée');
    expect(normaliserStatut('Approuvee', EXPENSE_STATUS)).toBe('Approuvée');
    expect(normaliserStatut('Remboursee', EXPENSE_STATUS)).toBe('Remboursée');
  });

  it('laisse passer un statut déjà correct', () => {
    for (const statut of EXPENSE_STATUS) {
      expect(normaliserStatut(statut, EXPENSE_STATUS)).toBe(statut);
    }
  });

  it('tolère la casse et les espaces autour', () => {
    expect(normaliserStatut('  refusée ', EXPENSE_STATUS)).toBe('Refusée');
    expect(normaliserStatut('EN ATTENTE', EXPENSE_STATUS)).toBe('En attente');
  });

  it('rend null sur un statut réellement inconnu', () => {
    // À l'appelant de choisir un repli : deviner ici masquerait une donnée
    // corrompue derrière une valeur plausible.
    expect(normaliserStatut('Brouillon', EXPENSE_STATUS)).toBeNull();
    expect(normaliserStatut('', EXPENSE_STATUS)).toBeNull();
    expect(normaliserStatut(null, EXPENSE_STATUS)).toBeNull();
  });

  it('sert aussi les factures', () => {
    expect(normaliserStatut('Validee', INVOICE_STATUS)).toBe('Validée');
    expect(normaliserStatut('En cours de traitement', INVOICE_STATUS)).toBe(
      'En cours de traitement',
    );
    // Un statut de note n'est pas un statut de facture.
    expect(normaliserStatut('Approuvee', INVOICE_STATUS)).toBeNull();
  });
});
