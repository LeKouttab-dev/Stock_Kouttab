import { z } from 'zod';
import { EXPENSE_STATUS } from '../constants';

/**
 * Le rattachement libre a disparu : pôle, événement et date de l'événement le
 * remplacent, et sont désormais obligatoires. Un ticket sans ces trois champs
 * arrivait chez le comptable sous un nom incomplet, impossible à imputer.
 *
 * L'événement accepte deux formes, exactement comme sur les factures : un
 * identifiant HelloAsso, ou une saisie libre pour ce qui n'existe pas chez eux
 * (achat courant, dépense d'intendance). L'un des deux suffit, jamais aucun.
 */
export const expenseSchema = z
  .object({
    date_depense: z.string().min(1, 'Date obligatoire'),
    fournisseur: z.string().min(1, 'Fournisseur obligatoire'),
    nature_charge: z.string().optional().or(z.literal('')),
    montant: z.coerce.number().positive('Le montant doit être > 0'),
    commentaires: z.string().optional().or(z.literal('')),
    remboursement_deja_emis: z.coerce.number().min(0).default(0),
    remise: z.coerce.number().min(0).default(0),
    id_pole: z
      .number({ invalid_type_error: 'Pôle de rattachement obligatoire' })
      .int()
      .positive('Pôle de rattachement obligatoire'),
    id_event: z.number().int().positive().nullable().optional(),
    evenement_libre: z.string().optional().or(z.literal('')),
    date_evenement: z.string().min(1, "Date de l'événement obligatoire"),
  })
  .refine((v) => Boolean(v.id_event) || Boolean(v.evenement_libre?.trim()), {
    message: 'Événement obligatoire : choisissez-en un ou saisissez son nom',
    path: ['id_event'],
  });

export type ExpenseFormValues = z.infer<typeof expenseSchema>;

/**
 * Édition d'une note « En attente » : seuls les champs de la dépense elle-même.
 *
 * Le rattachement comptable — pôle, événement, date — est volontairement absent.
 * Il compose le nom du justificatif déjà transmis à la comptabilité, et ce nom
 * est figé au dépôt : le modifier six mois plus tard désalignerait le fichier
 * déjà reçu par le comptable. Même raisonnement que sur les factures.
 */
export const expenseEditSchema = z.object({
  date_depense: z.string().min(1, 'Date obligatoire'),
  fournisseur: z.string().min(1, 'Fournisseur obligatoire'),
  nature_charge: z.string().optional().or(z.literal('')),
  montant: z.coerce.number().positive('Le montant doit être > 0'),
  commentaires: z.string().optional().or(z.literal('')),
  remboursement_deja_emis: z.coerce.number().min(0).default(0),
  remise: z.coerce.number().min(0).default(0),
});

export type ExpenseEditFormValues = z.infer<typeof expenseEditSchema>;

export const expenseValidateSchema = z.object({
  status: z.enum(EXPENSE_STATUS),
  commentaires_compta: z.string().optional().or(z.literal('')),
});

export type ExpenseValidateFormValues = z.infer<typeof expenseValidateSchema>;
