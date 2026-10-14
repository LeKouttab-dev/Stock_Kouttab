import { describe, expect, it } from 'vitest';
import {
  HAUTEUR_MIN,
  MINUTE_DEBUT,
  MINUTE_FIN,
  colonneDe,
  disposer,
  enHeure,
  fusionnerMicroCreneaux,
  minutesParis,
  placer,
  repartirEnVoies,
  type BlocGrille,
} from '@/lib/calendrier-grille';
import type { EvenementCalendrier } from '@/types/api';

let compteur = 0;

function evenement(partiel: Partial<EvenementCalendrier>): EvenementCalendrier {
  compteur += 1;
  return {
    id: `e${compteur}`,
    agenda_id: 'a',
    agenda_nom: 'Agenda',
    titre: 'Cours',
    debut: '2026-10-14T17:00:00+02:00',
    fin: '2026-10-14T18:30:00+02:00',
    journee_entiere: false,
    recurrent: false,
    nom_court: 'Agenda',
    ...partiel,
  };
}

function bloc(debutMinutes: number, finMinutes: number, cle = `b${debutMinutes}`): BlocGrille {
  return { cle, evenements: [evenement({})], debutMinutes, finMinutes, jour: '2026-10-14' };
}

describe('minutesParis', () => {
  it("lit l'heure de Paris même quand la machine tourne en UTC", () => {
    // L'intégration continue tourne en UTC : sans fuseau forcé, un cours de
    // 17:30 s'afficherait à 15:30 et rien ne le signalerait. C'est le bug
    // déjà corrigé sur `formatPlage`, à ne pas réintroduire ici.
    const instant = minutesParis('2026-10-14T17:30:00+02:00');
    expect(instant.jour).toBe('2026-10-14');
    expect(instant.minutes).toBe(17 * 60 + 30);
  });

  it('lit une heure donnée en UTC dans le fuseau de Paris', () => {
    const instant = minutesParis('2026-10-14T15:30:00Z');
    expect(instant.minutes).toBe(17 * 60 + 30);
  });

  it("traverse le changement d'heure d'automne", () => {
    // Le 25 octobre 2026, Paris repasse de UTC+2 à UTC+1.
    expect(minutesParis('2026-10-24T20:00:00Z').minutes).toBe(22 * 60);
    expect(minutesParis('2026-10-26T20:00:00Z').minutes).toBe(21 * 60);
  });
});

describe('placer', () => {
  it('pose une carte proportionnellement à son horaire', () => {
    const position = placer(17 * 60 + 30, 18 * 60 + 30);
    expect(position).toEqual({ top: (17 * 60 + 30 - MINUTE_DEBUT) * 1, hauteur: 60 });
  });

  it('rogne ce qui déborde de la grille', () => {
    const avant = placer(7 * 60, 9 * 60);
    expect(avant).toEqual({ top: 0, hauteur: 60 });
    const apres = placer(22 * 60, 23 * 60 + 30);
    expect(apres?.top).toBe((22 * 60 - MINUTE_DEBUT) * 1);
    expect(apres?.hauteur).toBe(MINUTE_FIN - 22 * 60);
  });

  it('impose une hauteur minimale pour qu’un créneau court reste cliquable', () => {
    expect(placer(12 * 60, 12 * 60 + 5)?.hauteur).toBe(HAUTEUR_MIN);
  });

  it('rend null pour ce qui tombe entièrement hors de la grille', () => {
    // Ces événements ne sont pas perdus : l'écran les met dans une bande
    // « hors plage ». Mais ils n'ont pas de place dans la grille.
    expect(placer(5 * 60, 6 * 60)).toBeNull();
    expect(placer(23 * 60, 23 * 60 + 30)).toBeNull();
  });
});

describe('repartirEnVoies', () => {
  it('laisse une seule voie quand rien ne se chevauche', () => {
    const places = repartirEnVoies([bloc(540, 600), bloc(600, 660), bloc(700, 760)]);
    expect(places.every((p) => p.voies === 1 && p.voie === 0)).toBe(true);
  });

  it('partage la largeur entre deux blocs qui se chevauchent', () => {
    const places = repartirEnVoies([bloc(540, 660, 'x'), bloc(600, 720, 'y')]);
    expect(places.map((p) => p.voies)).toEqual([2, 2]);
    expect(places.map((p) => p.voie).sort()).toEqual([0, 1]);
  });

  it('donne la même largeur à toute une grappe, même en chaîne', () => {
    // A∩B, B∩C, mais A et C ne se touchent pas : ils forment malgré tout une
    // seule grappe. Des largeurs différentes dans la même bande se liraient
    // comme un bug d'affichage.
    const places = repartirEnVoies([bloc(540, 620, 'a'), bloc(600, 700, 'b'), bloc(660, 740, 'c')]);
    expect(new Set(places.map((p) => p.voies))).toEqual(new Set([2]));
  });

  it('encaisse huit événements simultanés', () => {
    // Observé sur les données réelles dans la colonne « Autre », qui
    // rassemble tout ce qui n'a pas de salle.
    const blocs = Array.from({ length: 8 }, (_, i) => bloc(600, 700, `s${i}`));
    const places = repartirEnVoies(blocs);
    expect(places.every((p) => p.voies === 8)).toBe(true);
    expect(new Set(places.map((p) => p.voie)).size).toBe(8);
  });

  it('réutilise une voie libérée', () => {
    const places = repartirEnVoies([bloc(540, 600, 'a'), bloc(550, 650, 'b'), bloc(600, 660, 'c')]);
    const parCle = Object.fromEntries(places.map((p) => [p.bloc.cle, p.voie]));
    // « c » commence quand « a » finit : il reprend sa voie plutôt que d'en
    // ouvrir une troisième.
    expect(parCle.c).toBe(parCle.a);
  });
});

describe('fusionnerMicroCreneaux', () => {
  const permanence = (debut: string, fin: string) =>
    evenement({
      agenda_id: 'permanences',
      titre: 'Permanence administrative (paiement)',
      debut: `2026-10-17T${debut}:00+02:00`,
      fin: `2026-10-17T${fin}:00+02:00`,
    });

  it('regroupe les rendez-vous de cinq minutes en une seule plage', () => {
    // Sans cela, vingt filets d'un pixel que personne ne peut ni lire ni
    // cliquer.
    const blocs = fusionnerMicroCreneaux([
      permanence('12:00', '12:05'),
      permanence('12:05', '12:10'),
      permanence('12:25', '12:30'),
    ]);
    expect(blocs).toHaveLength(1);
    expect(blocs[0].evenements).toHaveLength(3);
    expect(blocs[0].debutMinutes).toBe(12 * 60);
    expect(blocs[0].finMinutes).toBe(12 * 60 + 30);
  });

  it('laisse un cours entier intact', () => {
    const blocs = fusionnerMicroCreneaux([
      evenement({ debut: '2026-10-14T17:30:00+02:00', fin: '2026-10-14T18:30:00+02:00' }),
    ]);
    expect(blocs).toHaveLength(1);
    expect(blocs[0].evenements).toHaveLength(1);
  });

  it('ne fusionne jamais deux agendas différents', () => {
    const blocs = fusionnerMicroCreneaux([
      permanence('12:00', '12:05'),
      evenement({
        agenda_id: 'autre-agenda',
        debut: '2026-10-17T12:05:00+02:00',
        fin: '2026-10-17T12:10:00+02:00',
      }),
    ]);
    expect(blocs).toHaveLength(2);
  });

  it('coupe la plage quand l’écart devient grand', () => {
    const blocs = fusionnerMicroCreneaux([
      permanence('12:00', '12:05'),
      permanence('16:00', '16:05'),
    ]);
    expect(blocs).toHaveLength(2);
  });

  it('ne fusionne pas deux cours d’une heure qui se suivent', () => {
    const blocs = fusionnerMicroCreneaux([
      evenement({ debut: '2026-10-14T17:00:00+02:00', fin: '2026-10-14T18:00:00+02:00' }),
      evenement({ debut: '2026-10-14T18:00:00+02:00', fin: '2026-10-14T19:00:00+02:00' }),
    ]);
    expect(blocs).toHaveLength(2);
  });
});

describe('colonneDe', () => {
  const salles = { maziri: 'Imam Maziri', nafi: "Imam Nafi'", zarrouq: 'Imam Zarrouq' };

  it('range un événement dans sa salle', () => {
    expect(colonneDe(evenement({ salle: 'maziri' }), salles)).toBe('maziri');
  });

  it('range en Maziri ce qui n’a pas de salle', () => {
    // Plus de colonne « Autre » : la première salle du référentiel recueille.
    expect(colonneDe(evenement({ salle: null }), salles)).toBe('maziri');
  });

  it('range en Maziri une salle que la grille ne connaît pas', () => {
    // Une colonne fantôme serait pire qu'une carte mal rangée.
    expect(colonneDe(evenement({ salle: 'autre' }), salles)).toBe('maziri');
  });
});

describe('enHeure', () => {
  it('formate les minutes depuis minuit', () => {
    expect(enHeure(17 * 60 + 30)).toBe('17:30');
    expect(enHeure(8 * 60)).toBe('08:00');
  });
});

describe('disposer', () => {
  const cours = (d: number, f: number, cle: string) => bloc(d, f, cle);
  const plage = (d: number, f: number, cle: string): BlocGrille => ({
    ...bloc(d, f, cle),
    evenements: [evenement({}), evenement({})],
  });

  it('pose les rendez-vous courts PAR-DESSUS le cours, qui garde toute la largeur', () => {
    // Mercredi 14/10, Maziri : Coran 17:30–19:30 et deux rendez-vous à 17:30.
    // Côte à côte, le cours tombait à « C… ».
    const places = disposer([
      cours(17 * 60 + 30, 19 * 60 + 30, 'coran'),
      bloc(17 * 60 + 30, 17 * 60 + 35, 'rdv1'),
      plage(17 * 60 + 30, 17 * 60 + 40, 'rdv2'),
    ]);
    const parCle = Object.fromEntries(places.map((p) => [p.bloc.cle, p]));
    expect(parCle.coran).toMatchObject({ gauche: 0, largeur: 100 });
    for (const cle of ['rdv1', 'rdv2']) {
      expect(parCle[cle].gauche).toBeGreaterThanOrEqual(50);
      expect(parCle[cle].plan).toBeGreaterThan(parCle.coran.plan);
    }
  });

  it('les créneaux posés sur un cours se partagent la zone de droite sans se recouvrir', () => {
    const places = disposer([
      cours(600, 720, 'cours'),
      bloc(600, 605, 'a'),
      bloc(600, 605, 'b'),
    ]).filter((p) => p.bloc.cle !== 'cours');
    const [a, b] = places.sort((x, y) => x.gauche - y.gauche);
    expect(a.gauche + a.largeur).toBeLessThanOrEqual(b.gauche + 0.001);
    expect(b.gauche + b.largeur).toBeLessThanOrEqual(100.001);
  });

  it('deux vrais cours au même moment restent côte à côte', () => {
    // Deux cours dans la même salle au même moment est un conflit réel :
    // le montrer côte à côte est juste.
    const places = disposer([cours(600, 720, 'x'), cours(630, 750, 'y')]);
    expect(places.map((p) => p.largeur)).toEqual([50, 50]);
  });

  it('un créneau court sans cours dessous prend toute la largeur', () => {
    // Rien à préserver : inutile de perdre la moitié de la place.
    const [seul] = disposer([bloc(720, 725, 'seul')]);
    expect(seul).toMatchObject({ gauche: 0, largeur: 100 });
  });

  it('un rendez-vous qui finit pile au début du cours est quand même posé dessus', () => {
    // 13:25–13:30 est dessiné sur plus de vingt minutes de grille : il déborde
    // sur le cours de 13:30. Le juger « libre » le mettait pleine largeur
    // par-dessus le titre « Madrassah N 2 ».
    const places = disposer([cours(13 * 60 + 30, 17 * 60, 'madrassah'), bloc(13 * 60 + 25, 13 * 60 + 30, 'rdv')]);
    const rdv = places.find((p) => p.bloc.cle === 'rdv');
    expect(rdv?.gauche).toBeGreaterThanOrEqual(50);
  });

  it('le cours sait ce que les créneaux posés couvrent de son haut', () => {
    // La carte descend son titre d'autant, pour qu'il reste lisible.
    const places = disposer([cours(13 * 60 + 30, 17 * 60, 'madrassah'), bloc(13 * 60 + 30, 13 * 60 + 35, 'rdv')]);
    const madrassah = places.find((p) => p.bloc.cle === 'madrassah');
    expect(madrassah?.retraitHaut).toBeGreaterThan(0);
  });

  it('un cours sans rien posé dessus ne décale rien', () => {
    const [seul] = disposer([cours(600, 720, 'seul')]);
    expect(seul.retraitHaut).toBe(0);
  });
});
