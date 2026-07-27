import { z } from 'zod';
import { EXPENSE_STATUS } from '../constants';

export const expenseSchema = z.object({
  date_depense: z.string().min(1, 'Date obligatoire'),
  rattachement: z.string().min(1, 'Rattachement obligatoire'),
  fournisseur: z.string().optional().or(z.literal('')),
  nature_charge: z.string().optional().or(z.literal('')),
  montant: z.coerce.number().positive('Le montant doit être > 0'),
  commentaires: z.string().optional().or(z.literal('')),
  remboursement_deja_emis: z.coerce.number().min(0).default(0),
  remise: z.coerce.number().min(0).default(0),
});

export type ExpenseFormValues = z.infer<typeof expenseSchema>;

export const expenseValidateSchema = z.object({
  status: z.enum(EXPENSE_STATUS),
  commentaires_compta: z.string().optional().or(z.literal('')),
});

export type ExpenseValidateFormValues = z.infer<typeof expenseValidateSchema>;
