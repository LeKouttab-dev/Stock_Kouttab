import { describe, expect, it } from 'vitest';
import { ajouterJours, ajouterMois, bornesPreset, jourDeParis, periodeInitiale } from './periode';

// 10/10/2026 à 12 h UTC (14 h à Paris).
const MIDI = new Date('2026-10-10T12:00:00Z');

describe('lib/periode', () => {
  it('le jour est celui de Paris, pas celui du navigateur', () => {
    // 22 h 30 UTC le 10 = 0 h 30 à Paris le 11.
    expect(jourDeParis(new Date('2026-10-10T22:30:00Z'))).toBe('2026-10-11');
    expect(jourDeParis(new Date('2026-10-10T21:30:00Z'))).toBe('2026-10-10');
  });

  it('calcule chaque préréglage', () => {
    expect(bornesPreset('aujourdhui', MIDI)).toEqual({ debut: '2026-10-10', fin: '2026-10-10' });
    expect(bornesPreset('7j', MIDI)).toEqual({ debut: '2026-10-04', fin: '2026-10-10' });
    expect(bornesPreset('mois', MIDI)).toEqual({ debut: '2026-10-01', fin: '2026-10-10' });
    expect(bornesPreset('3mois', MIDI)).toEqual({ debut: '2026-07-11', fin: '2026-10-10' });
  });

  it('personnalisé garde les dates en cours', () => {
    expect(bornesPreset('perso', MIDI, { debut: '2026-09-02', fin: '2026-09-05' })).toEqual({
      debut: '2026-09-02',
      fin: '2026-09-05',
    });
    expect(periodeInitiale('perso', MIDI)).toEqual({
      preset: 'perso',
      debut: '2026-10-01',
      fin: '2026-10-10',
    });
  });

  it('les décalages franchissent mois et années', () => {
    expect(ajouterJours('2026-01-03', -6)).toBe('2025-12-28');
    expect(ajouterMois('2026-05-31', -3)).toBe('2026-02-28');
    expect(ajouterMois('2026-01-15', -3)).toBe('2025-10-15');
    // À 0 h 30 à Paris le 1er novembre, « ce mois-ci » est novembre.
    expect(bornesPreset('mois', new Date('2026-10-31T23:30:00Z')).debut).toBe('2026-11-01');
  });
});
