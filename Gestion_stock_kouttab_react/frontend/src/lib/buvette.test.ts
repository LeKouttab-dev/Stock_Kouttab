import { describe, expect, it } from 'vitest';
import {
  emailValide,
  formatDepuis,
  formatEcart,
  lireEuros,
  periodeGlissante,
  tabletteSilencieuse,
  tonEcart,
} from './buvette';

describe('lib/buvette', () => {
  it('formatDepuis : secondes, minutes, heures, jours, jamais', () => {
    expect(formatDepuis(40)).toBe('il y a 40 s');
    expect(formatDepuis(125)).toBe('il y a 2 min');
    expect(formatDepuis(7200)).toBe('il y a 2 h');
    expect(formatDepuis(3 * 86400)).toBe('il y a 3 j');
    expect(formatDepuis(null)).toBe('jamais vue');
  });

  it('tabletteSilencieuse : au-delà de 5 minutes, ou jamais vue', () => {
    expect(tabletteSilencieuse(300)).toBe(false);
    expect(tabletteSilencieuse(301)).toBe(true);
    expect(tabletteSilencieuse(null)).toBe(true);
  });

  it('tonEcart et formatEcart', () => {
    expect(tonEcart(0)).toBe('juste');
    expect(tonEcart(-500)).toBe('leger');
    expect(tonEcart(501)).toBe('fort');
    expect(formatEcart(150)).toBe('+1,50 €');
    expect(formatEcart(-200)).toBe('−2,00 €');
    expect(formatEcart(0)).toBe('0,00 €');
  });

  it('lireEuros : virgule ou point, deux décimales au plus', () => {
    expect(lireEuros('12,50')).toBe(12.5);
    expect(lireEuros(' 12.5 ')).toBe(12.5);
    expect(lireEuros('0')).toBe(0);
    expect(lireEuros('12,505')).toBeNull();
    expect(lireEuros('-3')).toBeNull();
    expect(lireEuros('abc')).toBeNull();
    expect(lireEuros('')).toBeNull();
  });

  it('periodeGlissante : n jours, aujourd’hui compris', () => {
    expect(periodeGlissante(7, new Date(2026, 9, 9))).toEqual({
      debut: '2026-10-03',
      fin: '2026-10-09',
    });
  });

  it('emailValide', () => {
    expect(emailValide('omar@lekouttab.fr')).toBe(true);
    expect(emailValide('omar@')).toBe(false);
  });
});
