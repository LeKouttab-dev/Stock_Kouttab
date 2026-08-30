import { describe, expect, it } from 'vitest';
import { ACTIONS, canAccess, hasAnyRole, pageParDefaut } from './auth';
import type { Role } from './constants';

describe('lib/auth — canAccess', () => {
  it('Super Admin can do everything except Benevole-only actions (STOCK_REQUEST_MOD)', () => {
    // STOCK_REQUEST_MOD est intentionnellement réservé aux Bénévoles : un Super
    // Admin fait des modifs directes (STOCK_DIRECT_MOD), il n'a pas à passer par
    // la file de validation. C'est une décision produit, pas un bug.
    const benevoleOnly = new Set<string>([ACTIONS.STOCK_REQUEST_MOD]);
    for (const action of Object.values(ACTIONS)) {
      const expected = !benevoleOnly.has(action);
      expect(canAccess('Super Admin', action), `action=${action}`).toBe(expected);
    }
  });

  it('Benevole cannot access admin features', () => {
    expect(canAccess('Benevole', ACTIONS.ADMIN_VALIDATE_USERS)).toBe(false);
    expect(canAccess('Benevole', ACTIONS.ADMIN_MANAGE_USERS)).toBe(false);
    expect(canAccess('Benevole', ACTIONS.ADMIN_DATABASE)).toBe(false);
    expect(canAccess('Benevole', ACTIONS.STOCK_DIRECT_MOD)).toBe(false);
    expect(canAccess('Benevole', ACTIONS.EXPENSES_VALIDATE)).toBe(false);
  });

  it('Benevole CAN view stock and submit expenses', () => {
    expect(canAccess('Benevole', ACTIONS.STOCK_VIEW)).toBe(true);
    expect(canAccess('Benevole', ACTIONS.EXPENSES_SUBMIT)).toBe(true);
    expect(canAccess('Benevole', ACTIONS.STOCK_REQUEST_MOD)).toBe(true);
  });

  it('Compta can validate expenses but not directly modify stock', () => {
    expect(canAccess('Compta', ACTIONS.EXPENSES_VALIDATE)).toBe(true);
    expect(canAccess('Compta', ACTIONS.EXPENSES_VIEW_RIB)).toBe(true);
    expect(canAccess('Compta', ACTIONS.STOCK_DIRECT_MOD)).toBe(false);
  });

  it('AdminBenevoles can CRUD stock but not validate users', () => {
    expect(canAccess('AdminBenevoles', ACTIONS.STOCK_CRUD)).toBe(true);
    expect(canAccess('AdminBenevoles', ACTIONS.STOCK_DIRECT_MOD)).toBe(true);
    expect(canAccess('AdminBenevoles', ACTIONS.ADMIN_VALIDATE_USERS)).toBe(false);
    expect(canAccess('AdminBenevoles', ACTIONS.BUVETTE_WEBHOOK)).toBe(false);
  });

  it('returns false for null/undefined role', () => {
    expect(canAccess(null, ACTIONS.STOCK_VIEW)).toBe(false);
    expect(canAccess(undefined, ACTIONS.STOCK_VIEW)).toBe(false);
  });
});

describe('lib/auth — BenevoleFrais (confine aux notes de frais)', () => {
  it('ne peut que deposer et suivre ses notes de frais', () => {
    expect(canAccess('BenevoleFrais', ACTIONS.EXPENSES_SUBMIT)).toBe(true);
    for (const action of Object.values(ACTIONS)) {
      if (action === ACTIONS.EXPENSES_SUBMIT) continue;
      expect(canAccess('BenevoleFrais', action), `action=${action}`).toBe(false);
    }
  });

  it('sa page par defaut est /expenses, celle des autres /dashboard', () => {
    expect(pageParDefaut('BenevoleFrais')).toBe('/expenses');
    expect(pageParDefaut('Benevole')).toBe('/dashboard');
    expect(pageParDefaut('Super Admin')).toBe('/dashboard');
    expect(pageParDefaut(null)).toBe('/login');
  });

  it('les roles complets gardent profil et contact, pas lui', () => {
    expect(canAccess('Benevole', ACTIONS.PROFILE_VIEW)).toBe(true);
    expect(canAccess('Benevole', ACTIONS.CONTACT_VIEW)).toBe(true);
    expect(canAccess('BenevoleFrais', ACTIONS.PROFILE_VIEW)).toBe(false);
    expect(canAccess('BenevoleFrais', ACTIONS.CONTACT_VIEW)).toBe(false);
  });
});

describe('lib/auth — hasAnyRole', () => {
  it('returns true when role is in the allowlist', () => {
    const allowed: Role[] = ['Super Admin', 'Compta'];
    expect(hasAnyRole('Compta', allowed)).toBe(true);
  });

  it('returns false otherwise', () => {
    expect(hasAnyRole('Benevole', ['Super Admin'])).toBe(false);
    expect(hasAnyRole(null, ['Super Admin'])).toBe(false);
  });
});
