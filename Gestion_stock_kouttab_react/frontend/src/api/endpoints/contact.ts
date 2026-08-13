import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '../client';
import type { Conversation, ContactCible, ConversationStatut } from '@/types/api';

/**
 * Fils de discussion de l'espace de contact.
 *
 * Le destinataire n'est qu'un mot-clé : le serveur seul connaît les adresses.
 * Envoyer l'adresse depuis le navigateur ferait de l'endpoint un relais ouvert.
 */
export const conversationQueryKeys = {
  all: ['conversations'] as const,
  mine: () => [...conversationQueryKeys.all, 'mine'] as const,
  team: () => [...conversationQueryKeys.all, 'team'] as const,
  detail: (id: number) => [...conversationQueryKeys.all, 'detail', id] as const,
};

export interface ConversationPayload {
  destinataire: ContactCible;
  sujet: string;
  message: string;
}

async function fetchMine(): Promise<Conversation[]> {
  const { data } = await api.get<Conversation[]>('/conversations');
  return data;
}

async function fetchTeam(): Promise<Conversation[]> {
  const { data } = await api.get<Conversation[]>('/conversations/equipe');
  return data;
}

async function fetchOne(id: number): Promise<Conversation> {
  const { data } = await api.get<Conversation>(`/conversations/${id}`);
  return data;
}

async function openConversation(payload: ConversationPayload): Promise<Conversation> {
  const { data } = await api.post<Conversation>('/conversations', payload);
  return data;
}

async function reply(params: { id: number; corps: string }): Promise<Conversation> {
  const { data } = await api.post<Conversation>(`/conversations/${params.id}/messages`, {
    corps: params.corps,
  });
  return data;
}

async function setStatut(params: { id: number; statut: ConversationStatut }) {
  const { data } = await api.patch<Conversation>(`/conversations/${params.id}/statut`, {
    statut: params.statut,
  });
  return data;
}

async function transfer(params: { id: number; destinataire: ContactCible }) {
  const { data } = await api.patch<Conversation>(`/conversations/${params.id}/destinataire`, {
    destinataire: params.destinataire,
  });
  return data;
}

export function useMyConversations() {
  return useQuery({ queryKey: conversationQueryKeys.mine(), queryFn: fetchMine });
}

export function useTeamConversations(enabled = true) {
  return useQuery({ queryKey: conversationQueryKeys.team(), queryFn: fetchTeam, enabled });
}

/**
 * Le fil ouvert.
 *
 * L'appel ne sert pas qu'à charger les messages : côté serveur, il éteint la
 * pastille du demandeur. Ouvrir un fil, c'est l'avoir lu.
 */
export function useConversation(id: number | null) {
  return useQuery({
    queryKey: conversationQueryKeys.detail(id ?? 0),
    queryFn: () => fetchOne(id as number),
    enabled: id !== null,
  });
}

/** Les compteurs du menu bougent à chaque écriture : on les invalide aussi. */
function useConversationMutation<TVars, TData>(mutationFn: (v: TVars) => Promise<TData>) {
  const qc = useQueryClient();
  return useApiMutation({
    mutationFn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: conversationQueryKeys.all });
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useOpenConversation() {
  return useConversationMutation(openConversation);
}

export function useReplyToConversation() {
  return useConversationMutation(reply);
}

export function useSetConversationStatut() {
  return useConversationMutation(setStatut);
}

export function useTransferConversation() {
  return useConversationMutation(transfer);
}
