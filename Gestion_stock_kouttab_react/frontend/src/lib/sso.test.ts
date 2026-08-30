import { describe, expect, it } from 'vitest';
import { jetonDepuisFragment } from './sso';

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
