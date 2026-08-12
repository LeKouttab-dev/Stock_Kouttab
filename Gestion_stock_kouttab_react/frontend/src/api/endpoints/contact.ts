import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';

/**
 * Espace de contact.
 *
 * Le destinataire n'est qu'un mot-clé : le serveur seul connaît les adresses.
 * Envoyer l'adresse depuis le navigateur ferait de l'endpoint un relais ouvert.
 */
export type ContactCible = 'compta' | 'admin';

export interface ContactPayload {
  destinataire: ContactCible;
  sujet: string;
  message: string;
}

async function sendContact(payload: ContactPayload): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>('/contact', payload);
  return data;
}

export function useSendContact() {
  return useApiMutation({ mutationFn: sendContact });
}
