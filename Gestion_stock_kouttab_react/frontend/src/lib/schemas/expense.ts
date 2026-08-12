import { z } from 'zod';
import { EXPENSE_STATUS } from '../constants';

/**
 * Le rattachement libre a disparu : le pôle et ce qu'il commande le remplacent.
 * Un ticket sans rattachement arrivait chez le comptable sous un nom incomplet,
 * impossible à imputer.
 *
 * Ce que le pôle commande, précisément :
 * - **pôle événementiel** → un événement (identifiant HelloAsso ou saisie libre
 *   pour ce qui n'existe pas chez eux) et sa date ;
 * - **tout autre pôle** → une catégorie (courses, goûter, matériel...) et une
 *   description de l'achat. Une dépense du local n'a pas d'événement, et en
 *   exiger un obligeait à en inventer.
 *
 * `requiert_evenement` est un champ technique, recopié depuis le pôle
 * sélectionné : Zod valide un objet et ne connaît pas le référentiel des pôles.
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
    requiert_evenement: z.boolean().default(false),
    id_event: z.number().int().positive().nullable().optional(),
    evenement_libre: z.string().optional().or(z.literal('')),
    date_evenement: z.string().optional().or(z.literal('')),
    id_categorie: z.number().int().positive().nullable().optional(),
  })
  .superRefine((v, ctx) => {
    if (v.requiert_evenement) {
      if (!v.id_event && !v.evenement_libre?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['id_event'],
          message: 'Événement obligatoire : choisissez-en un ou saisissez son nom',
        });
      }
      if (!v.date_evenement?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['date_evenement'],
          message: "Date de l'événement obligatoire",
        });
      }
      return;
    }

    if (!v.id_categorie) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['id_categorie'],
        message: 'Catégorie obligatoire',
      });
    }
    if (!v.commentaires?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['commentaires'],
        message: "Décrivez l'achat",
      });
    }
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
