import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { RoleBadge } from '@/components/shared/RoleBadge';
import { usePendingUsers, useValidateUser, useDeleteUser } from '@/api/endpoints/users';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

export function PendingUsersSection() {
  const { data: pending = [], isLoading } = usePendingUsers();
  const validate = useValidateUser();
  const remove = useDeleteUser();
  const toast = useToast();

  const handleApprove = (id: number) => {
    validate.mutate({ id, status: 'active' }, { onSuccess: () => toast.success('Compte validé') });
  };

  const handleRefuse = (id: number) => {
    remove.mutate(id, { onSuccess: () => toast.info('Compte refusé et supprimé') });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{fr.admin.validationComptes}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-24" />
        ) : pending.length === 0 ? (
          <EmptyState title={fr.admin.aucuneDemandeCompte} />
        ) : (
          <ul className="space-y-2">
            {pending.map((u) => (
              <li
                key={u.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-muted/20 px-3 py-2"
              >
                <div>
                  <p className="font-medium">
                    {u.prenom} {u.nom} (@{u.username})
                  </p>
                  <p className="text-xs text-muted-foreground">{u.email}</p>
                </div>
                <RoleBadge role={u.role} />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => handleApprove(u.id)}
                    loading={validate.isPending}
                  >
                    {fr.admin.approuver}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRefuse(u.id)}
                    loading={remove.isPending}
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
