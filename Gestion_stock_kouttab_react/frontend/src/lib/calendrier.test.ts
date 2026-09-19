import { describe, expect, it } from 'vitest';
import { contrasteSur, formatPlage } from '@/lib/calendrier';
import type { EvenementCalendrier } from '@/types/api';

function evenement(partiel: Partial<EvenementCalendrier>): EvenementCalendrier {
  return {
    id: 'e',
    agenda_id: 'a',
    agenda_nom: 'Agenda',
    titre: 'Cours',
    debut: '2026-09-21T17:00:00+02:00',
    fin: '2026-09-21T18:30:00+02:00',
    journee_entiere: false,
    recurrent: false,
    ...partiel,
  };
}

describe('contrasteSur', () => {
  it('écrit en sombre sur les couleurs claires de Google', () => {
    // Le jaune « Banana » : du blanc dessus est illisible.
    expect(contrasteSur('#f6bf26')).toBe('#1f2937');
  });

  it('écrit en blanc sur les couleurs foncées', () => {
    expect(contrasteSur('#0b8043')).toBe('#ffffff');
  });

  it('retombe sur le blanc quand la couleur est absente ou inattendue', () => {
    expect(contrasteSur(null)).toBe('#ffffff');
    expect(contrasteSur('rouge')).toBe('#ffffff');
  });
});

describe('formatPlage', () => {
  it("donne les horaires de Paris, quel que soit le fuseau de l'appareil", () => {
    // L'intégration tourne en UTC : sans fuseau explicite, ce cours de 17 h
    // s'afficherait à 15 h pour elle, et pour tout bénévole en déplacement.
    const texte = formatPlage(evenement({}));
    expect(texte).toContain('17:00');
    expect(texte).toContain('18:30');
  });

  it('ne fait pas déborder une journée entière sur le lendemain', () => {
    // Google rend une fin EXCLUSIVE : le 22 pour un événement du seul 21.
    const texte = formatPlage(
      evenement({ journee_entiere: true, debut: '2026-09-21', fin: '2026-09-22' }),
    );
    expect(texte).toContain('toute la journée');
    expect(texte).not.toContain('22');
  });

  it('garde les deux bornes quand la journée entière en couvre plusieurs', () => {
    const texte = formatPlage(
      evenement({ journee_entiere: true, debut: '2026-09-21', fin: '2026-09-24' }),
    );
    expect(texte).toContain('21');
    expect(texte).toContain('23');
  });
});
