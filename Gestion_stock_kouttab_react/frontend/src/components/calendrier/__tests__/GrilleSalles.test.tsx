import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GrilleSalles } from '../GrilleSalles';
import type { EvenementCalendrier } from '@/types/api';

const SALLES = {
  maziri: 'Imam Maziri',
  nafi: "Imam Nafi'",
  zarrouq: 'Imam Zarrouq',
};

let compteur = 0;

function evenement(partiel: Partial<EvenementCalendrier>): EvenementCalendrier {
  compteur += 1;
  return {
    id: `e${compteur}`,
    agenda_id: 'coran',
    agenda_nom: 'Coran - enfants 1 U.soundousse 2026/2027',
    titre: 'cours 19',
    debut: '2026-10-14T17:30:00+02:00',
    fin: '2026-10-14T18:30:00+02:00',
    journee_entiere: false,
    recurrent: false,
    nom_court: 'Coran ENF 1',
    numero: '19',
    enseignant: 'U. Soundousse',
    couleur: '#4986e7',
    ...partiel,
  };
}

function afficher(evenements: EvenementCalendrier[], options: { parSalle?: boolean } = {}) {
  return render(
    <GrilleSalles
      jours={['2026-10-14']}
      evenements={evenements}
      salles={SALLES}
      sallesVisibles={Object.keys(SALLES)}
      parSalle={options.parSalle ?? true}
      maintenant={null}
      onOuvrir={vi.fn()}
    />,
  );
}

describe('GrilleSalles', () => {
  it('ne montre que les salles occupées ce jour-là, dans l’ordre du référentiel', () => {
    afficher([
      evenement({ salle: 'zarrouq', salle_source: 'google' }),
      evenement({ salle: 'maziri', salle_source: 'google' }),
    ]);
    const colonnes = screen.getAllByRole('region');
    // Nafi' n'a aucun cours : pas de colonne vide qui prendrait la place.
    expect(colonnes).toHaveLength(2);
    expect(colonnes[0]).toHaveAccessibleName(/Imam Maziri/);
    expect(colonnes[1]).toHaveAccessibleName(/Imam Zarrouq/);
  });

  it('un jour sans aucun cours garde une colonne', () => {
    // Sinon il disparaîtrait de la semaine : jour vide ou jour manquant ?
    afficher([]);
    expect(screen.getAllByRole('region')).toHaveLength(1);
    expect(screen.getByRole('region')).toHaveAccessibleName(/aucun cours/);
  });

  it('place un cours dans la salle réservée', () => {
    afficher([evenement({ salle: 'nafi', salle_libelle: "Imam Nafi'", salle_source: 'google' })]);
    const colonne = screen.getByRole('region', { name: /Imam Nafi'/ });
    expect(within(colonne).getByRole('button')).toBeInTheDocument();
  });

  it('range en Maziri, en pointillés, ce qui n’a pas de salle', () => {
    // Le serveur envoie `salle: maziri, salle_source: defaut`. La carte doit
    // être là — et dire qu'elle n'y est que par défaut.
    afficher([
      evenement({ salle: 'maziri', salle_libelle: 'Imam Maziri', salle_source: 'defaut' }),
    ]);
    const colonne = screen.getByRole('region', { name: /Imam Maziri/ });
    expect(within(colonne).getByRole('button')).toHaveAccessibleName(
      /par défaut, aucune salle renseignée/,
    );
  });

  it('affiche le nom d’agenda raccourci, pas le titre Google', () => {
    // Le titre Google est « cours 19 » : illisible seul.
    afficher([evenement({ salle: 'maziri' })]);
    expect(screen.getByText('Coran ENF 1')).toBeInTheDocument();
    // Le numéro seul, sans « № » — cherché dans la carte, la gouttière des
    // heures affichant elle aussi « 19 ».
    const carte = screen.getByRole('button');
    expect(within(carte).getByText('19')).toBeInTheDocument();
    expect(carte.textContent).not.toContain('№');
    expect(screen.getByText('U. Soundousse')).toBeInTheDocument();
  });

  it('dit qu’une salle devinée n’est pas réservée', () => {
    afficher([
      evenement({
        salle: 'maziri',
        salle_libelle: 'Imam Maziri',
        salle_source: 'correspondance',
      }),
    ]);
    expect(
      screen.getByRole('button', { name: /salle habituelle, non réservée dans Google/ }),
    ).toBeInTheDocument();
  });

  it('ne le dit pas quand la salle est réellement réservée', () => {
    afficher([
      evenement({ salle: 'maziri', salle_libelle: 'Imam Maziri', salle_source: 'google' }),
    ]);
    const carte = screen.getByRole('button');
    expect(carte).toHaveAccessibleName(/Imam Maziri/);
    expect(carte).not.toHaveAccessibleName(/non réservée/);
  });

  it('le nom accessible porte la vérité non tronquée', () => {
    // La carte visible tient sur trois lignes courtes ; ce que lit un lecteur
    // d'écran ne doit pas l'être.
    afficher([evenement({ salle: 'maziri' })]);
    expect(screen.getByRole('button')).toHaveAccessibleName(
      /Coran - enfants 1 U\.soundousse 2026\/2027, séance 19, U\. Soundousse, de 17:30 à 18:30/,
    );
  });

  it('fusionne les rendez-vous de cinq minutes en un seul bloc', () => {
    const permanence = (debut: string, fin: string) =>
      evenement({
        agenda_id: 'permanences',
        agenda_nom: 'Permanence administrative 2026/2027',
        nom_court: 'Perm. admin.',
        numero: null,
        enseignant: null,
        titre: 'Permanence administrative (paiement)',
        debut: `2026-10-14T${debut}:00+02:00`,
        fin: `2026-10-14T${fin}:00+02:00`,
      });
    afficher([permanence('12:00', '12:05'), permanence('12:05', '12:10'), permanence('12:25', '12:30')]);

    // Une seule carte, et elle annonce son compte.
    const cartes = screen.getAllByRole('button');
    expect(cartes).toHaveLength(1);
    expect(cartes[0]).toHaveAccessibleName(/3 créneaux/);
  });

  it('sans découpage par salle, il ne reste qu’une colonne par jour', () => {
    afficher([evenement({ salle: 'maziri' })], { parSalle: false });
    expect(screen.getAllByRole('region')).toHaveLength(1);
  });

  it('signale ce qui tombe hors de la plage horaire', () => {
    // Un cours de 6 h ne doit pas disparaître sans bruit.
    afficher([
      evenement({ debut: '2026-10-14T06:00:00+02:00', fin: '2026-10-14T07:00:00+02:00' }),
    ]);
    expect(screen.getByText(/1 hors plage/)).toBeInTheDocument();
  });

  it('les cartes d’une colonne sont dans l’ordre chronologique dans le DOM', () => {
    // Elles sont posées en absolu : l'ordre visuel ne guide la tabulation que
    // si l'ordre du DOM le suit.
    afficher([
      evenement({ salle: 'maziri', nom_court: 'Tard', debut: '2026-10-14T19:00:00+02:00', fin: '2026-10-14T20:00:00+02:00' }),
      evenement({ salle: 'maziri', nom_court: 'Tot', debut: '2026-10-14T09:00:00+02:00', fin: '2026-10-14T10:00:00+02:00' }),
    ]);
    const colonne = screen.getByRole('region', { name: /Imam Maziri/ });
    const textes = within(colonne)
      .getAllByRole('button')
      .map((b) => b.textContent);
    expect(textes[0]).toContain('Tot');
    expect(textes[1]).toContain('Tard');
  });
});
