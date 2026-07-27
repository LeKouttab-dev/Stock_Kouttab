import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Download, Search } from 'lucide-react';
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
  getInvoiceFileUrl,
  useInvoices,
  useUpdateInvoiceStatus,
} from '@/api/endpoints/invoices';
import { INVOICE_STATUS, type InvoiceStatus } from '@/lib/constants';
import type { Invoice } from '@/types/api';
import { useAuth } from '@/hooks/useAuth';
import { ACTIONS } from '@/lib/auth';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

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
        <h1 className="text-2xl font-bold">📋 {fr.invoices.listeFactures}</h1>
        <p className="text-sm text-muted-foreground">Filtrez et consultez les factures déposées.</p>
      </div>

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
                        📄 Facture #{inv.id} —{' '}
                        {inv.files?.[0]?.nom_fichier ?? '—'}{' '}
                        ({formatDate(inv.date_depot)})
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
  const update = useUpdateInvoiceStatus();
  const toast = useToast();
  const [status, setStatus] = useState<InvoiceStatus>(invoice.status);

  const onUpdate = async () => {
    try {
      await update.mutateAsync({ id: invoice.id, status });
      toast.success('Statut mis à jour');
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  return (
    <div className="border-t bg-muted/10 px-4 py-4 space-y-3 text-sm">
      <div className="grid gap-1 md:grid-cols-2">
        <p>
          <strong>{fr.invoices.deposeePar} :</strong> {invoice.prenom} {invoice.nom}
        </p>
        <p>
          <strong>{fr.invoices.dateDepot} :</strong> {formatDate(invoice.date_depot)}
        </p>
        <p>
          <strong>{fr.invoices.nombreFichiers} :</strong> {invoice.files?.length ?? 0}
        </p>
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
            {invoice.files.map((f) => (
              <li key={f.id}>
                <a
                  href={getInvoiceFileUrl(invoice.id, f.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <Download className="h-3.5 w-3.5" />
                  {f.nom_fichier}
                </a>
              </li>
            ))}
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
    </div>
  );
}
