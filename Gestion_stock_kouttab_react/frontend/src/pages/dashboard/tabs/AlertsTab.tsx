import { Mail, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { KpiCard } from '@/components/shared/KpiCard';
import { useLowStock, useSendStockAlert } from '@/api/endpoints/stock';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { fr } from '@/lib/i18n/fr';

export function AlertsTab() {
  const { data: items = [], isLoading } = useLowStock();
  const sendAlert = useSendStockAlert();
  const toast = useToast();

  const critical = items.filter((i) => i.quantite === 0).length;
  const low = items.filter((i) => i.quantite > 0).length;

  const handleSend = async () => {
    try {
      const res = await sendAlert.mutateAsync();
      toast.success(
        'Email envoyé',
        `Notifié ${res.recipients} responsable(s) pour ${res.items} article(s).`,
      );
    } catch (err) {
      toast.error('Erreur', extractErrorMessage(err));
    }
  };

  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (items.length === 0) {
    return (
      <Alert variant="success">
        <CheckCircle2 className="h-4 w-4" />
        <AlertTitle>Tout est OK</AlertTitle>
        <AlertDescription>{fr.dashboard.aucunAlerte}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <Alert variant="warning">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          🚨 {items.length} {fr.dashboard.articlesNecessitentAttention}
        </AlertDescription>
      </Alert>

      <div className="grid gap-3 md:grid-cols-2">
        <KpiCard label={fr.dashboard.articlesCritiques} value={critical} variant="danger" />
        <KpiCard label={fr.dashboard.articlesBas} value={low} variant="warning" />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Article</TableHead>
                <TableHead>Catégorie</TableHead>
                <TableHead>Sous-cat.</TableHead>
                <TableHead className="text-right">Quantité</TableHead>
                <TableHead className="text-right">Seuil</TableHead>
                <TableHead>Criticité</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id}>
                  <TableCell className="font-medium">
                    <span className="mr-1">{it.emoji ?? '📦'}</span>
                    {it.nom}
                  </TableCell>
                  <TableCell>{it.categorie}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {it.sous_categorie ?? '—'}
                  </TableCell>
                  <TableCell className="text-right font-mono">{it.quantite}</TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">
                    {it.seuil_alerte}
                  </TableCell>
                  <TableCell>
                    {it.quantite === 0 ? (
                      <span className="font-medium text-red-600">🔴 Critique</span>
                    ) : (
                      <span className="font-medium text-terracotta-600">🟡 Bas</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold">{fr.dashboard.actionsRapides}</p>
            <p className="text-sm text-muted-foreground">
              Notifier les administrateurs bénévoles & le Super Admin par email.
            </p>
          </div>
          <Button onClick={handleSend} loading={sendAlert.isPending}>
            <Mail className="h-4 w-4" />
            {fr.dashboard.envoyerEmail}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
