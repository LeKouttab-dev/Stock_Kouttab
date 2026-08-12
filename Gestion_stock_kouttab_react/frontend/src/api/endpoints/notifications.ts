/**
 * Ce qui attend l'utilisateur : pastilles du menu et rappel de connexion.
 *
 * Un seul appel sert les deux. Les compteurs arrivent déjà filtrés par les
 * droits du demandeur — l'interface n'a rien à masquer, un 0 veut dire « rien
 * à traiter » aussi bien que « pas concerné ».
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '../client';
import type { PendingSummary } from '@/types/api';

export const notificationQueryKeys = {
  all: ['notifications'] as const,
  summary: () => [...notificationQueryKeys.all, 'summary'] as const,
};

async function fetchPendingSummary(): Promise<PendingSummary> {
  const { data } = await api.get<PendingSummary>('/notifications/summary');
  return data;
}

export function usePendingSummary() {
  return useQuery({
    queryKey: notificationQueryKeys.summary(),
    queryFn: fetchPendingSummary,
    // Les pastilles doivent suivre le traitement des dossiers sans imposer un
    // rechargement de page, sans pour autant interroger le serveur en boucle.
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

/** Somme des dossiers qui demandent une action, alertes de stock exclues. */
export function totalAtraiter(resume: PendingSummary | undefined): number {
  if (!resume) return 0;
  return (
    resume.notes_a_valider +
    resume.factures_a_traiter +
    resume.modifications_stock +
    resume.comptes_a_valider
  );
}
