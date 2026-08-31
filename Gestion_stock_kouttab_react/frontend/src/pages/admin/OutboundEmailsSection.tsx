import { AlertTriangle, CheckCircle2, RefreshCw, Send } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { useEtatEnvois, useOutboundEmails, useRetryOutboundEmail } from '@/api/endpoints/admin';
import { useToast } from '@/hooks/useToast';
import { formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import type { OutboundEmailStatus } from '@/types/api';

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
/**
 * État du circuit d'envoi, en tête de la file.
 *
 * La liste seule ne suffit pas : elle ne montre que les envois comptables, et
 * reste verte quand le serveur SMTP ne répond plus — les notifications de dépôt,
 * elles, ne laissent aucune ligne derrière elles. C'est ainsi que la production
 * a passé plusieurs semaines sans émettre un seul courriel, sans qu'aucun écran
 * ne le dise.
 */
function EtatBanniere() {
  const { data: etat } = useEtatEnvois();
  if (!etat) return null;

  const motifs = [
    !etat.email_enabled && fr.outbox.etatDesactive,
    etat.email_enabled && !etat.smtp_joignable && etat.smtp_erreur,
    etat.destinataires_compta.length === 0 && fr.outbox.etatSansDestinataire,
  ].filter((m): m is string => Boolean(m));

  if (motifs.length === 0) {
    return (
      <p className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
        {fr.outbox.etatOk}
      </p>
    );
  }

  return (
    <div
      role="alert"
      className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm"
    >
      <p className="flex items-center gap-2 font-medium text-destructive">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
        {fr.outbox.etatCoupe}
      </p>
      <ul className="mt-1 space-y-0.5 pl-6 text-xs text-destructive">
        {motifs.map((motif) => (
          <li key={motif}>{motif}</li>
        ))}
      </ul>
    </div>
  );
}

export function OutboundEmailsSection() {
  const toast = useToast();

  const { data: emails = [], isLoading, refetch } = useOutboundEmails();
  const retry = useRetryOutboundEmail();

  const onRetry = (id: number) => {
    retry.mutate(id, { onSuccess: () => toast.success(fr.invoices.renvoiSucces) });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Send className="h-4 w-4" aria-hidden />
              {fr.outbox.title}
            </CardTitle>
            <p className="text-xs text-muted-foreground">{fr.outbox.subtitle}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
            {fr.common.refresh}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <EtatBanniere />
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
