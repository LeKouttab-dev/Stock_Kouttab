import { z } from 'zod';
import { INVOICE_STATUS } from '../constants';

/**
 * Dépôt d'une facture.
 *
 * Ce que le formulaire demande dépend du pôle choisi, et le pôle seul en
 * décide : sous le pôle événementiel, un événement et sa date ; sous les
 * autres — le local, l'institut — une catégorie (courses, goûter, matériel...)
 * et une description de l'achat. Une dépense du local n'a aucun événement, et
 * en exiger un obligeait à en inventer.
 *
 * `requiertEvenement` est un champ technique, recopié depuis le pôle
 * sélectionné : Zod valide un objet et ne connaît pas le référentiel des pôles.
 */
export const invoiceUploadSchema = z
  .object({
    comment: z.string().optional().or(z.literal('')),
    poleId: z
      .number({ required_error: 'Le pôle est obligatoire' })
      .int()
      .positive('Le pôle est obligatoire'),
    requiertEvenement: z.boolean().default(false),
    // Exactement l'un des deux : événement du référentiel OU saisie libre.
    eventId: z.number().int().positive().nullable().optional(),
    eventLibre: z.string().optional(),
    dateEvenement: z.string().optional(),
    categorieId: z.number().int().positive().nullable().optional(),
    fournisseur: z.string().optional(),
    montant: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.requiertEvenement) {
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
      if (!values.dateEvenement?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['dateEvenement'],
          message: "La date de l'événement est obligatoire",
        });
      }
      return;
    }

    if (!values.categorieId) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['categorieId'],
        message: 'La catégorie est obligatoire',
      });
    }
    if (!values.comment?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['comment'],
        message: "Décrivez l'achat",
      });
    }
  });

export type InvoiceUploadFormValues = z.infer<typeof invoiceUploadSchema>;

export const invoiceStatusSchema = z.object({
  status: z.enum(INVOICE_STATUS),
});

export type InvoiceStatusFormValues = z.infer<typeof invoiceStatusSchema>;
