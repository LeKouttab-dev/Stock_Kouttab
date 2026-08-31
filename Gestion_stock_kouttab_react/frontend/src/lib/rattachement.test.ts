import { describe, expect, it } from 'vitest';
import { evenementParTitre, polePourEvenement, polesSansEvenement } from './rattachement';
import type { AppEvent, Pole } from '@/types/api';

/**
 * Le pôle se déduit de l'événement, plus l'inverse.
 *
 * Avant : on choisissait un pôle EV, puis la liste d'événements était filtrée
 * par sa famille. Rien n'empêchait de poser une dépense « Sortie à la ferme (J) »
 * sous EV(T) — la famille étant saisie à la main, la plupart des événements
 * importés n'en avaient aucune et apparaissaient donc sous les trois pôles.
 */

const pole = (p: Partial<Pole> & { id: number; nom: string }): Pole =>
  ({
    is_default: false,
    is_active: true,
    ordre: 0,
    requiert_evenement: false,
    type_evenement: null,
    ...p,
  }) as Pole;

const POLES: Pole[] = [
  pole({ id: 4, nom: 'EV(T)', requiert_evenement: true, type_evenement: 'T' }),
  pole({ id: 5, nom: 'EV(G)', requiert_evenement: true, type_evenement: 'G' }),
  pole({ id: 6, nom: 'EV(J)', requiert_evenement: true, type_evenement: 'J' }),
  pole({ id: 7, nom: 'Frais généraux' }),
  pole({ id: 8, nom: 'Halaqa' }),
  // Désactivé : conservé pour les pièces anciennes, jamais reproposé.
  pole({ id: 1, nom: 'Pôle événementiel', requiert_evenement: true, is_active: false }),
];

describe('lib/rattachement', () => {
  it('associe chaque famille à son pôle', () => {
    expect(polePourEvenement(POLES, 'J')?.nom).toBe('EV(J)');
    expect(polePourEvenement(POLES, 'T')?.nom).toBe('EV(T)');
    expect(polePourEvenement(POLES, 'G')?.nom).toBe('EV(G)');
  });

  it('tolère une lettre minuscule ou entourée d’espaces', () => {
    // La lettre vient d'un titre saisi à la main chez HelloAsso.
    expect(polePourEvenement(POLES, 'j')?.nom).toBe('EV(J)');
    expect(polePourEvenement(POLES, ' T ')?.nom).toBe('EV(T)');
  });

  it('rend la main quand la famille est absente', () => {
    // Un événement non étiqueté reste déposable : le formulaire demande alors
    // le pôle, au lieu de bloquer.
    expect(polePourEvenement(POLES, null)).toBeNull();
    expect(polePourEvenement(POLES, undefined)).toBeNull();
    expect(polePourEvenement(POLES, '')).toBeNull();
  });

  it('rend la main quand aucun pôle actif ne porte la famille', () => {
    expect(polePourEvenement(POLES, 'X')).toBeNull();
  });

  it('ne tranche pas entre deux pôles de la même famille', () => {
    /* Configuration ambiguë : en choisir un au hasard imputerait faux un jour
       sur deux, et l'erreur ne se verrait qu'à la clôture. */
    const ambigu = [
      ...POLES,
      pole({ id: 9, nom: 'EV(J) bis', requiert_evenement: true, type_evenement: 'J' }),
    ];
    expect(polePourEvenement(ambigu, 'J')).toBeNull();
  });

  it('ignore un pôle désactivé', () => {
    const seulementInactif = [
      pole({
        id: 1,
        nom: 'EV(T) retiré',
        requiert_evenement: true,
        type_evenement: 'T',
        is_active: false,
      }),
    ];
    expect(polePourEvenement(seulementInactif, 'T')).toBeNull();
  });

  it('ne propose que les pôles sans événement pour une dépense hors événement', () => {
    /* Les pôles EV ne s'atteignent plus qu'en choisissant l'événement : les
       laisser ici permettrait de poser EV(T) sans aucun événement, ce que
       l'API refuse ensuite avec un message que rien à l'écran n'explique. */
    expect(polesSansEvenement(POLES).map((p) => p.nom)).toEqual(['Frais généraux', 'Halaqa']);
  });
});

/**
 * Le passage signé depuis l'outil de gestion transporte un TITRE, pas un
 * identifiant. Le reconnaître dans le référentiel rattache la pièce à la vraie
 * ligne — et son `type_ev`, déjà déduit par le backend, désigne alors le pôle
 * sans qu'un second lecteur de « (T)/(G)/(J) » ait à exister ici.
 */
const evenement = (id: number, nom: string, type_ev: string | null = null): AppEvent =>
  ({ id, nom, type_ev, source: 'helloasso', is_active: true }) as AppEvent;

const EVENTS: AppEvent[] = [
  evenement(3, '16/08 - Sortie pédagogique à la ferme (J)', 'J'),
  evenement(6, "Août 26 - Stage de Qur'an Hommes (T)", 'T'),
];

describe('lib/rattachement — reconnaissance par titre', () => {
  it('retrouve l’événement dont le titre correspond', () => {
    expect(evenementParTitre(EVENTS, '16/08 - Sortie pédagogique à la ferme (J)')?.id).toBe(3);
  });

  it('tolère espaces en trop et différences de casse', () => {
    // Les titres en base portent des espaces de fin ; le passage peut les perdre.
    expect(evenementParTitre(EVENTS, '  16/08 -  Sortie   pédagogique à la ferme (J)  ')?.id).toBe(
      3,
    );
  });

  it('rend la main quand rien ne correspond', () => {
    /* Le titre part alors en saisie libre, comme avant : reconnaître à peu près
       rattacherait la pièce au mauvais événement, ce qui ne se verrait qu'à la
       clôture. */
    expect(evenementParTitre(EVENTS, 'Un événement inconnu (G)')).toBeNull();
    expect(evenementParTitre(EVENTS, '')).toBeNull();
    expect(evenementParTitre(EVENTS, null)).toBeNull();
    expect(evenementParTitre(undefined, 'Peu importe')).toBeNull();
  });

  it('ne devine pas entre deux événements homonymes', () => {
    const doublons = [...EVENTS, evenement(9, '16/08 - Sortie pédagogique à la ferme (J)', 'J')];
    expect(evenementParTitre(doublons, '16/08 - Sortie pédagogique à la ferme (J)')).toBeNull();
  });

  it('le titre reconnu mène au pôle, sans rien parser côté front', () => {
    // Le bout-en-bout du passage signé : titre → événement → famille → pôle.
    const trouve = evenementParTitre(EVENTS, "Août 26 - Stage de Qur'an Hommes (T)");
    expect(polePourEvenement(POLES, trouve?.type_ev)?.nom).toBe('EV(T)');
  });
});
