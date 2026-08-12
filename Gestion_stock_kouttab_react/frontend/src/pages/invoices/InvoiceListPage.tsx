import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, ClipboardList, Download, Search, Send } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { EmptyState } from '@/components/shared/EmptyState';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { KpiCard } from '@/components/shared/KpiCard';
import {
  useInvoices,
  useResendComptaEmail,
  useUpdateInvoiceStatus,
} from '@/api/endpoints/invoices';
import { INVOICE_STATUS, type InvoiceStatus } from '@/lib/constants';
import type { Invoice } from '@/types/api';
import { useAuth } from '@/hooks/useAuth';
import { ACTIONS } from '@/lib/auth';
import { buildAttachmentFilename, deduplicateFilenames } from '@/lib/naming';
import { useDownloadAttachment } from '@/hooks/useDownloadAttachment';
import { useToast } from '@/hooks/useToast';
import { formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { TicketsManagementSection } from './TicketsManagementSection';

export function InvoiceListPage() {
  const [statusFilter, setStatusFilter] = useState<string>('Toutes');
  const [search, setSearch] = useState('');
  const [date, setDate] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);

  const { data: invoices = [], isLoading } = useInvoices({
    status: statusFilter === 'Toutes' ? undefined : statusFilter,
    date: date || undefined,
    search: search || undefined,
  });

  const stats = useMemo(
    () => ({
      total: invoices.length,
      enAttente: invoices.filter((i) => i.status === 'En attente').length,
      enCours: invoices.filter((i) => i.status === 'En cours de traitement').length,
      validees: invoices.filter((i) => i.status === 'Validée').length,
    }),
    [invoices],
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <ClipboardList className="h-6 w-6" aria-hidden />
          {fr.invoices.listeFactures}
        </h1>
        <p className="text-sm text-muted-foreground">Filtrez et consultez les factures déposées.</p>
      </div>

      {/* Les demandes de justificatif vivent ici : c'est en parcourant les
          pièces reçues que la comptabilité constate ce qui manque. */}
      <TicketsManagementSection />

      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-3">
          <div>
            <Label>{fr.invoices.filtrerStatut}</Label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Toutes">Toutes</SelectItem>
                {INVOICE_STATUS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>{fr.invoices.filtrerDate}</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <Label>{fr.invoices.rechercher}</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="nom de fichier…"
                className="pl-9"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-4">
        <KpiCard label={fr.invoices.totalFactures} value={stats.total} variant="info" />
        <KpiCard label={fr.invoices.enAttente} value={stats.enAttente} variant="warning" />
        <KpiCard label={fr.invoices.enCours} value={stats.enCours} variant="info" />
        <KpiCard label={fr.invoices.validees} value={stats.validees} variant="success" />
      </div>

      {isLoading ? (
        <LoadingSpinner fullPage />
      ) : invoices.length === 0 ? (
        <EmptyState title={fr.invoices.aucuneFacture} />
      ) : (
        <div className="space-y-3">
          {invoices.map((inv) => {
            const isOpen = expanded === inv.id;
            return (
              <Card key={inv.id}>
                <CardContent className="p-0">
                  <button
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30"
                    onClick={() => setExpanded(isOpen ? null : inv.id)}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      )}
                      <span className="truncate font-medium">
                        Facture #{inv.id} — {inv.files?.[0]?.nom_fichier ?? '—'} (
                        {formatDate(inv.date_depot)})
                      </span>
                    </div>
                    <StatusBadge status={inv.status} />
                  </button>
                  {isOpen && <InvoiceDetail invoice={inv} />}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function InvoiceDetail({ invoice }: { invoice: Invoice }) {
  const { can } = useAuth();
  const canChange = can(ACTIONS.INVOICES_CHANGE_STATUS);
  const canResend = can(ACTIONS.COMPTA_RESEND_EMAIL);
  const update = useUpdateInvoiceStatus();
  const resend = useResendComptaEmail();
  const toast = useToast();
  const { download, downloadingId } = useDownloadAttachment();

  // Mêmes noms que ceux reçus par le comptable, cf. ValidateExpensesPage.
  const comptaNames = useMemo(() => {
    const files = invoice.files ?? [];
    if (files.length === 0) return [];
    return deduplicateFilenames(
      files.map((f) =>
        buildAttachmentFilename(
          [invoice.pole, invoice.evenement],
          invoice.date_evenement || invoice.date_depot || null,
          f.nom_fichier.split('.').pop() || 'pdf',
        ),
      ),
    );
  }, [invoice]);
  const [status, setStatus] = useState<InvoiceStatus>(invoice.status);

  const onUpdate = () => {
    update.mutate(
      { id: invoice.id, status },
      { onSuccess: () => toast.success('Statut mis à jour') },
    );
  };

  const onResend = () => {
    resend.mutate(invoice.id, { onSuccess: () => toast.success(fr.invoices.renvoiSucces) });
  };

  return (
    <div className="border-t bg-muted/10 px-4 py-4 space-y-3 text-sm">
      <div className="grid gap-1 md:grid-cols-2">
        <p>
          {/* `user_full_name`, et non `prenom`/`nom` : l'API ne renvoie pas ces
              deux champs sur une facture, si bien que la ligne restait vide —
              impossible de savoir qui avait déposé la pièce. Le repli sur les
              champs séparés couvre d'anciennes réponses en cache. */}
          <strong>{fr.invoices.deposeePar} :</strong>{' '}
          {invoice.user_full_name || [invoice.prenom, invoice.nom].filter(Boolean).join(' ') || '—'}
        </p>
        <p>
          <strong>{fr.invoices.dateDepot} :</strong> {formatDate(invoice.date_depot)}
        </p>
        <p>
          <strong>{fr.invoices.nombreFichiers} :</strong> {invoice.files?.length ?? 0}
        </p>
        {/* Rattachement comptable — absent des factures antérieures au module. */}
        {invoice.pole && (
          <p>
            <strong>{fr.invoices.pole} :</strong> {invoice.pole}
          </p>
        )}
        {invoice.evenement && (
          <p>
            <strong>{fr.invoices.evenement} :</strong> {invoice.evenement}
          </p>
        )}
        {invoice.date_evenement && (
          <p>
            <strong>{fr.invoices.dateEvenement} :</strong> {formatDate(invoice.date_evenement)}
          </p>
        )}
        {invoice.fournisseur && (
          <p>
            <strong>{fr.invoices.fournisseur} :</strong> {invoice.fournisseur}
          </p>
        )}
      </div>

      {invoice.commentaire && (
        <p>
          <strong>Commentaire :</strong> {invoice.commentaire}
        </p>
      )}

      {invoice.files && invoice.files.length > 0 && (
        <div className="space-y-1">
          <p className="font-medium">Fichiers :</p>
          <ul className="space-y-1">
            {invoice.files.map((f, index) => {
              const nomComptable = comptaNames[index] ?? f.nom_fichier;
              return (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() =>
                      download(`/invoices/${invoice.id}/files/${f.id}`, nomComptable, f.id)
                    }
                    disabled={downloadingId === f.id}
                    className="inline-flex items-center gap-1 text-primary hover:underline disabled:opacity-60"
                  >
                    <Download className="h-3.5 w-3.5" />
                    {nomComptable}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {canChange && (
        <div className="flex flex-wrap items-end gap-2 rounded-md border bg-background p-3">
          <div className="flex-1 min-w-[200px]">
            <Label>{fr.expenses.changerStatut}</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as InvoiceStatus)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INVOICE_STATUS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={onUpdate} loading={update.isPending}>
            {fr.common.update}
          </Button>
        </div>
      )}

      {/* Relance de l'envoi au comptable.
          Utile quand le serveur mail était injoignable au moment du dépôt, ou
          quand le comptable signale ne pas avoir reçu la pièce : on renvoie
          celle déjà déposée plutôt que de demander un second dépôt, qui créerait
          un doublon en base. La file réessaie seule pendant environ 2 h 30 puis
          abandonne — ce bouton reprend la main ensuite. */}
      {canResend && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-background p-3">
          <p className="text-xs text-muted-foreground">{fr.invoices.renvoyerAide}</p>
          <Button variant="outline" onClick={onResend} loading={resend.isPending}>
            <Send className="mr-1 h-4 w-4" />
            {fr.invoices.renvoyerMail}
          </Button>
        </div>
      )}
    </div>
  );
}
