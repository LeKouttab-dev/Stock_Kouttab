import { describe, expect, it } from 'vitest';
import { expenseSchema } from '../expense';
import { invoiceUploadSchema } from '../invoice';

/**
 * Ce que chaque pôle exige, vu du formulaire.
 *
 * La même règle est validée côté serveur (`crud/rattachement.py`) ; ces tests
 * garantissent que le formulaire refuse en amont ce que l'API refuserait, pour
 * que le déposant voie l'erreur sous le champ concerné plutôt qu'en bandeau
 * après un aller-retour réseau.
 */

const NOTE_BASE = {
  date_depense: '2026-08-12',
  fournisseur: 'Metro',
  montant: 24.9,
  remboursement_deja_emis: 0,
  remise: 0,
  id_pole: 1,
};

const FACTURE_BASE = {
  poleId: 1,
};

function chemins(resultat: ReturnType<typeof expenseSchema.safeParse>): string[] {
  if (resultat.success) return [];
  return resultat.error.issues.map((i) => i.path.join('.'));
}

describe('note de frais — pôle événementiel', () => {
  it('accepte un événement saisi librement et sa date', () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: true,
      evenement_libre: 'Gala',
      date_evenement: '2026-08-20',
    });
    expect(r.success).toBe(true);
  });

  it("refuse l'absence d'événement", () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: true,
      date_evenement: '2026-08-20',
    });
    expect(chemins(r)).toContain('id_event');
  });

  it("refuse l'absence de date d'événement", () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: true,
      evenement_libre: 'Gala',
    });
    expect(chemins(r)).toContain('date_evenement');
  });

  it("n'exige pas de description", () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: true,
      evenement_libre: 'Gala',
      date_evenement: '2026-08-20',
      commentaires: '',
    });
    expect(r.success).toBe(true);
  });
});

describe('note de frais — pôle sans événement', () => {
  it('accepte une catégorie et une description', () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: false,
      id_categorie: 3,
      commentaires: 'Eau et gobelets',
    });
    expect(r.success).toBe(true);
  });

  it("n'exige ni événement ni date d'événement", () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: false,
      id_categorie: 3,
      commentaires: 'Eau et gobelets',
      date_evenement: '',
    });
    expect(r.success).toBe(true);
  });

  it("refuse l'absence de catégorie", () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: false,
      commentaires: 'Eau et gobelets',
    });
    expect(chemins(r)).toContain('id_categorie');
  });

  it("exige la description de l'achat", () => {
    const r = expenseSchema.safeParse({
      ...NOTE_BASE,
      requiert_evenement: false,
      id_categorie: 3,
      commentaires: '   ',
    });
    expect(chemins(r)).toContain('commentaires');
  });
});

describe('facture — pôle sans événement', () => {
  it('accepte une catégorie et une description', () => {
    const r = invoiceUploadSchema.safeParse({
      ...FACTURE_BASE,
      requiertEvenement: false,
      categorieId: 2,
      comment: 'Papeterie pour le local',
    });
    expect(r.success).toBe(true);
  });

  it("refuse l'absence de catégorie", () => {
    const r = invoiceUploadSchema.safeParse({
      ...FACTURE_BASE,
      requiertEvenement: false,
      comment: 'Papeterie',
    });
    expect(r.success).toBe(false);
    if (!r.success) {
      expect(r.error.issues.map((i) => i.path.join('.'))).toContain('categorieId');
    }
  });
});

describe('facture — pôle événementiel', () => {
  it('exige toujours événement et date', () => {
    const r = invoiceUploadSchema.safeParse({
      ...FACTURE_BASE,
      requiertEvenement: true,
      comment: '',
    });
    expect(r.success).toBe(false);
    if (!r.success) {
      const paths = r.error.issues.map((i) => i.path.join('.'));
      expect(paths).toContain('eventId');
      expect(paths).toContain('dateEvenement');
    }
  });

  it('refuse un événement choisi ET saisi', () => {
    const r = invoiceUploadSchema.safeParse({
      ...FACTURE_BASE,
      requiertEvenement: true,
      eventId: 4,
      eventLibre: 'Gala',
      dateEvenement: '2026-08-20',
    });
    expect(r.success).toBe(false);
  });
});
