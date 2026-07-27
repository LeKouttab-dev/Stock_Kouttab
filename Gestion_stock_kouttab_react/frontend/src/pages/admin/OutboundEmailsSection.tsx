import { RefreshCw, Send } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { useApiMutation } from '@/hooks/useApiMutation';
import { api } from '@/api/client';
import { useToast } from '@/hooks/useToast';
import { formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import type { OutboundEmail, OutboundEmailStatus } from '@/types/api';

const outboxQueryKey = ['outbound-emails'] as const;

const STATUS_LABELS: Record<OutboundEmailStatus, string> = {
  pending: fr.outbox.pending,
  sending: fr.outbox.sending,
  sent: fr.outbox.sent,
  failed: fr.outbox.failed,
  abandoned: fr.outbox.abandoned,
};

const STATUS_VARIANTS: Record<
  OutboundEmailStatus,
  'default' | 'secondary' | 'outline' | 'destructive'
> = {
  pending: 'secondary',
  sending: 'secondary',
  sent: 'default',
  failed: 'destructive',
  abandoned: 'destructive',
};

/**
 * File des envois vers le service comptable.
 *
 * Rend visible ce qui ne l'était pas : un échec SMTP se constatait auparavant
 * des mois plus tard, en s'apercevant qu'une pièce manquait à la clôture.
 */
export function OutboundEmailsSection() {
  const qc = useQueryClient();
  const toast = useToast();

  const { data: emails = [], isLoading } = useQuery({
    queryKey: outboxQueryKey,
    queryFn: async () => {
      const { data } = await api.get<OutboundEmail[]>('/admin/outbound-emails', {
        params: { limit: 50 },
      });
      return data;
    },
  });

  const retry = useApiMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.post(`/admin/outbound-emails/${id}/retry`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: outboxQueryKey }),
  });

  const onRetry = async (id: number) => {
    await retry.mutateAsync(id);
    toast.success(fr.invoices.renvoiSucces);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">📤 {fr.outbox.title}</CardTitle>
            <p className="text-xs text-muted-foreground">{fr.outbox.subtitle}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: outboxQueryKey })}
          >
            <RefreshCw className="h-4 w-4" />
            {fr.common.refresh}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : emails.length === 0 ? (
          <EmptyState title={fr.outbox.empty} />
        ) : (
          <ul className="space-y-2">
            {emails.map((mail) => (
              <li key={mail.id} className="rounded-md border bg-muted/10 px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <Badge variant={STATUS_VARIANTS[mail.status]}>
                      {STATUS_LABELS[mail.status]}
                    </Badge>
                    <span className="font-medium">{mail.subject}</span>
                  </span>
                  {/* Un envoi abouti n'a pas à être relancé : ce serait un
                      doublon dans la boîte du comptable. */}
                  {mail.status !== 'sent' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onRetry(mail.id)}
                      loading={retry.isPending}
                    >
                      <Send className="mr-1 h-3.5 w-3.5" />
                      {fr.outbox.retry}
                    </Button>
                  )}
                </div>

                <p className="mt-1 text-xs text-muted-foreground">
                  {mail.recipient_list.join(', ') || fr.outbox.noRecipient} ·{' '}
                  {mail.attachment_names.length} {fr.outbox.attachments}
                  {mail.sent_at ? ` · ${fr.outbox.sentOn} ${formatDate(mail.sent_at)}` : ''}
                  {mail.attempts > 0 ? ` · ${mail.attempts}/${mail.max_attempts}` : ''}
                </p>

                {mail.last_error && (
                  <p className="mt-1 text-xs text-destructive">{mail.last_error}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
