import { describe, expect, it } from 'vitest';
import { jetonDepuisFragment, prefillDepuisFragment } from './sso';

/**
 * Le jeton de passage arrive dans le FRAGMENT de l'URL (#jeton=…) : le
 * fragment n'est jamais envoyé au serveur, donc jamais journalisé (Caddy et
 * le backend journalisent les URL complètes).
 */
describe('lib/sso — jetonDepuisFragment', () => {
  it('extrait le jeton du fragment', () => {
    expect(jetonDepuisFragment('#jeton=abc.DEF-123_x')).toBe('abc.DEF-123_x');
  });

  it('tolère un fragment à plusieurs paires', () => {
    expect(jetonDepuisFragment('#foo=1&jeton=aaa.bbb.ccc')).toBe('aaa.bbb.ccc');
  });

  it('rend null sans jeton', () => {
    expect(jetonDepuisFragment('')).toBeNull();
    expect(jetonDepuisFragment('#')).toBeNull();
    expect(jetonDepuisFragment('#autre=1')).toBeNull();
  });

  it('refuse les caractères hors alphabet JWT', () => {
    expect(jetonDepuisFragment('#jeton=<script>')).toBeNull();
  });
});

/**
 * Le passage peut porter, a cote du jeton, l'evenement du benevole — pour
 * preremplir la note de frais. Donnees d'affichage uniquement : rien de signe,
 * rien de sensible, l'utilisateur peut de toute facon tout editer.
 */
describe('lib/sso — prefillDepuisFragment', () => {
  it('extrait evenement et date', () => {
    const p = prefillDepuisFragment('#jeton=a.b.c&evenement=Kermesse%20(J)&date_evenement=2026-09-12');
    expect(p).toEqual({ evenement: 'Kermesse (J)', date_evenement: '2026-09-12' });
  });

  it('rend un objet vide sans prefill', () => {
    expect(prefillDepuisFragment('#jeton=a.b.c')).toEqual({});
    expect(prefillDepuisFragment('')).toEqual({});
  });

  it('ignore une date mal formee', () => {
    const p = prefillDepuisFragment('#jeton=a.b.c&evenement=Gala&date_evenement=demain');
    expect(p).toEqual({ evenement: 'Gala' });
  });

  it('borne la longueur de l evenement', () => {
    const long = 'x'.repeat(500);
    const p = prefillDepuisFragment(`#jeton=a.b.c&evenement=${long}`);
    expect((p.evenement ?? '').length).toBeLessThanOrEqual(255);
  });
});
