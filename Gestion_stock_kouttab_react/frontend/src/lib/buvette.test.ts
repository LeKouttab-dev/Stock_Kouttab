import { describe, expect, it } from 'vitest';
import {
  emailValide,
  formatDepuis,
  formatEcart,
  formatDateHeureParis,
  formatEcartUnites,
  jourParis,
  nomExportInventaires,
  libelleEcartEspeces,
  lireEuros,
  lireQuantite,
  nomFichierDepuisEntete,
  recapComptage,
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

  it('lireQuantite : entier positif ou nul, jamais négatif', () => {
    expect(lireQuantite('12')).toBe(12);
    expect(lireQuantite('012')).toBe(12);
    expect(lireQuantite('-4')).toBe(4);
    expect(lireQuantite('')).toBe(0);
    expect(lireQuantite('abc')).toBe(0);
    expect(lireQuantite('250000')).toBe(100000);
  });

  it('formatEcartUnites et libelleEcartEspeces', () => {
    expect(formatEcartUnites(2)).toBe('+2');
    expect(formatEcartUnites(-3)).toBe('−3');
    expect(formatEcartUnites(0)).toBe('0');
    expect(libelleEcartEspeces(250)).toBe('Surplus de 2,50 €');
    expect(libelleEcartEspeces(-300)).toBe('Manque 3,00 €');
    expect(libelleEcartEspeces(0)).toBe('Compte juste');
  });

  it('recapComptage : écarts, valeur et perte estimée', () => {
    const lignes = [
      { id: 1, nom: 'Coca', emoji: null, prix_cents: 150, stock_actuel: 5 },
      { id: 2, nom: 'Chips', emoji: null, prix_cents: 100, stock_actuel: 3 },
      { id: 3, nom: 'Eau', emoji: null, prix_cents: 50, stock_actuel: 0 },
      { id: 4, nom: 'Supprimé', emoji: null, prix_cents: 100, stock_actuel: null },
    ];
    const r = recapComptage(lignes, { 1: 2, 2: 3, 3: 4, 4: 9 });
    expect(r.ecarts.map((e) => [e.id, e.ecart, e.valeur_cents])).toEqual([
      [1, -3, -450],
      [3, 4, 200],
    ]);
    expect(r.ecartUnites).toBe(1);
    expect(r.valeurCents).toBe(-250);
    expect(r.perteCents).toBe(450);
  });

  it('nomFichierDepuisEntete', () => {
    expect(nomFichierDepuisEntete('attachment; filename="paiements-2026-10-01_2026-10-09.xlsx"')).toBe(
      'paiements-2026-10-01_2026-10-09.xlsx',
    );
    expect(nomFichierDepuisEntete("attachment; filename*=UTF-8''inventaire%C3%A9.xlsx")).toBe(
      'inventaireé.xlsx',
    );
    expect(nomFichierDepuisEntete('attachment; filename=a.xlsx')).toBe('a.xlsx');
    expect(nomFichierDepuisEntete(undefined)).toBeNull();
    expect(nomFichierDepuisEntete('attachment')).toBeNull();
  });

  it('heure de Paris et noms de fichiers par défaut', () => {
    expect(formatDateHeureParis('2026-10-09T20:03:35+00:00')).toBe('09/10/2026 22:03');
    expect(formatDateHeureParis('2026-01-15T23:30:00+00:00')).toBe('16/01/2026 00:30');
    expect(jourParis('2026-10-09T22:30:00+00:00')).toBe('2026-10-10');
    expect(nomExportInventaires('', '')).toBe('inventaires-tout.xlsx');
    expect(nomExportInventaires('2026-10-01', '')).toBe('inventaires-depuis-2026-10-01.xlsx');
    expect(nomExportInventaires('', '2026-10-31')).toBe('inventaires-jusqu-au-2026-10-31.xlsx');
    expect(nomExportInventaires('2026-10-01', '2026-10-31')).toBe(
      'inventaires-2026-10-01_2026-10-31.xlsx',
    );
  });
});
