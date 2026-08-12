import { z } from 'zod';

/**
 * Bornes calquées sur `schemas/contact.py` : un message rejeté côté serveur
 * après un envoi apparemment réussi est le pire des deux mondes.
 */
export const contactSchema = z.object({
  destinataire: z.enum(['compta', 'admin']),
  sujet: z.string().min(3, 'Objet trop court').max(150, 'Objet trop long'),
  message: z
    .string()
    .min(10, 'Décrivez votre question en quelques mots')
    .max(5000, 'Message trop long'),
});

export type ContactFormValues = z.infer<typeof contactSchema>;
