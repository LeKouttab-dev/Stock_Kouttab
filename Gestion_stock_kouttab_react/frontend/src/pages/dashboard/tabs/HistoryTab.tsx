import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { EmptyState } from '@/components/shared/EmptyState';
import { KpiCard } from '@/components/shared/KpiCard';
import { useStockModifications } from '@/api/endpoints/stock';
import { formatDateTime } from '@/lib/format';
import { STOCK_MOD_STATUS } from '@/lib/constants';
import { fr } from '@/lib/i18n/fr';

const PERIODS = [
  { value: '1', label: 'Dernières 24h' },
  { value: '7', label: '7 derniers jours' },
  { value: '30', label: '30 derniers jours' },
  { value: '90', label: '90 derniers jours' },
];

export function HistoryTab() {
  const [days, setDays] = useState('7');
  const [status, setStatus] = useState<string>('Tous');

  const { data: modifications = [], isLoading } = useStockModifications({
    days: Number(days),
    status: status === 'Tous' ? undefined : status,
  });

  const counts = useMemo(
    () => ({
      enAttente: modifications.filter((m) => m.status === 'En attente').length,
      approuvees: modifications.filter((m) => m.status === 'Approuvée').length,
      refusees: modifications.filter((m) => m.status === 'Refusée').length,
    }),
    [modifications],
  );

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <p className="text-sm font-medium">{fr.dashboard.periode}</p>
          <Select value={days} onValueChange={setDays}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-medium">{fr.dashboard.statut}</p>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Tous">Tous</SelectItem>
              {STOCK_MOD_STATUS.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <KpiCard label="En attente" value={counts.enAttente} variant="warning" />
        <KpiCard label="Approuvées" value={counts.approuvees} variant="success" />
        <KpiCard label="Refusées" value={counts.refusees} variant="danger" />
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6">
              <Skeleton className="h-40 w-full" />
            </div>
          ) : modifications.length === 0 ? (
            <EmptyState title={fr.dashboard.aucuneModification} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Demandeur</TableHead>
                  <TableHead>Article</TableHead>
                  <TableHead>Catégorie</TableHead>
                  <TableHead className="text-right">Actuelle</TableHead>
                  <TableHead className="text-right">Demandée</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {modifications.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>{formatDateTime(m.date_demande)}</TableCell>
                    <TableCell>
                      {m.user_prenom} {m.user_nom}
                    </TableCell>
                    <TableCell className="font-medium">{m.stock_nom}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {m.categorie}
                      {m.sous_categorie ? ` / ${m.sous_categorie}` : ''}
                    </TableCell>
                    <TableCell className="text-right">{m.quantite_actuelle}</TableCell>
                    <TableCell className="text-right font-medium">{m.quantite_demandee}</TableCell>
                    <TableCell>
                      <StatusBadge status={m.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
