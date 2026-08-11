import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import {
  useApproveModification,
  useRefuseModification,
  useStockModifications,
} from '@/api/endpoints/stock';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

export function PendingStockModsSection() {
  const { data: pending = [], isLoading } = useStockModifications({ status: 'En attente' });
  const approve = useApproveModification();
  const refuse = useRefuseModification();
  const toast = useToast();

  const handleApprove = (id: number) => {
    approve.mutate(id, { onSuccess: () => toast.success('Modification approuvée') });
  };

  const handleRefuse = (id: number) => {
    refuse.mutate(id, { onSuccess: () => toast.info('Modification refusée') });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{fr.admin.validationModifsStock}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : pending.length === 0 ? (
          <EmptyState title={fr.admin.aucuneModifStockEnAttente} />
        ) : (
          <ul className="space-y-3">
            {pending.map((m) => (
              <li key={m.id} className="rounded-md border bg-muted/10 p-3 space-y-2 text-sm">
                <p>
                  <strong>{fr.admin.demandeur} :</strong> {m.user_prenom} {m.user_nom}
                </p>
                <p>
                  <strong>{fr.admin.article} :</strong> {m.stock_nom}
                </p>
                <p>
                  <strong>{fr.admin.modifDemandee} :</strong> {m.quantite_actuelle} →{' '}
                  <strong>{m.quantite_demandee}</strong>
                </p>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => handleApprove(m.id)} loading={approve.isPending}>
                    {fr.admin.approuver}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRefuse(m.id)}
                    loading={refuse.isPending}
                  >
                    {fr.admin.refuser}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
