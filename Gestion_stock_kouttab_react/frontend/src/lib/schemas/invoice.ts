import { z } from 'zod';
import { INVOICE_STATUS } from '../constants';

export const invoiceUploadSchema = z
  .object({
    comment: z.string().optional().or(z.literal('')),
    poleId: z
      .number({ required_error: 'Le pôle est obligatoire' })
      .int()
      .positive('Le pôle est obligatoire'),
    // Exactement l'un des deux : événement du référentiel OU saisie libre.
    eventId: z.number().int().positive().nullable().optional(),
    eventLibre: z.string().optional(),
    dateEvenement: z.string().min(1, "La date de l'événement est obligatoire"),
    fournisseur: z.string().optional(),
    montant: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    const hasFree = Boolean(values.eventLibre?.trim());
    const hasSelected = values.eventId !== null && values.eventId !== undefined;
    if (!hasFree && !hasSelected) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['eventId'],
        message: "L'événement est obligatoire",
      });
    }
    if (hasFree && hasSelected) {
      // Le backend refuse aussi ce cas : mieux vaut le dire avant l'envoi.
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['eventId'],
        message: 'Choisissez un événement de la liste OU saisissez-en un',
      });
    }
  });

export type InvoiceUploadFormValues = z.infer<typeof invoiceUploadSchema>;

export const invoiceStatusSchema = z.object({
  status: z.enum(INVOICE_STATUS),
});

export type InvoiceStatusFormValues = z.infer<typeof invoiceStatusSchema>;
