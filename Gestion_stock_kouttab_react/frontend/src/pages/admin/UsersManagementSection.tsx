import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { RoleBadge } from '@/components/shared/RoleBadge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useDeleteUser, useUpdateUserRole, useUsers } from '@/api/endpoints/users';
import { useAuth } from '@/hooks/useAuth';
import { ROLES, ROLE_LABELS, type Role } from '@/lib/constants';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { fr } from '@/lib/i18n/fr';

export function UsersManagementSection() {
  const { data: users = [], isLoading } = useUsers();
  const { user: currentUser } = useAuth();
  const updateRole = useUpdateUserRole();
  const remove = useDeleteUser();
  const toast = useToast();
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [pendingRole, setPendingRole] = useState<Record<number, Role>>({});

  const others = users.filter((u) => u.id !== currentUser?.id);

  const handleRoleChange = async (id: number) => {
    const newRole = pendingRole[id];
    if (!newRole) return;
    try {
      await updateRole.mutateAsync({ id, role: newRole });
      toast.success(`Rôle mis à jour`);
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  const handleDelete = async () => {
    if (confirmDelete === null) return;
    try {
      await remove.mutateAsync(confirmDelete);
      toast.success('Utilisateur supprimé');
      setConfirmDelete(null);
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{fr.admin.gestionUtilisateurs}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32" />
          ) : others.length === 0 ? (
            <EmptyState title={fr.admin.aucunAutreUser} />
          ) : (
            <div className="space-y-3">
              {others.map((u) => {
                const selected = pendingRole[u.id] ?? u.role;
                return (
                  <div
                    key={u.id}
                    className="flex flex-col gap-3 rounded-md border bg-muted/10 p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="font-medium">
                        {u.prenom} {u.nom} <span className="text-muted-foreground">@{u.username}</span>
                      </p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <RoleBadge role={u.role} />
                      <Select
                        value={selected}
                        onValueChange={(v) =>
                          setPendingRole((cur) => ({ ...cur, [u.id]: v as Role }))
                        }
                      >
                        <SelectTrigger className="w-44">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((r) => (
                            <SelectItem key={r} value={r}>
                              {ROLE_LABELS[r]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        size="sm"
                        onClick={() => handleRoleChange(u.id)}
                        loading={updateRole.isPending}
                        disabled={selected === u.role}
                      >
                        {fr.admin.miseAJourRole}
                      </Button>
                      <Button
                        size="icon"
                        variant="outline"
                        onClick={() => setConfirmDelete(u.id)}
                        aria-label="Supprimer"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={confirmDelete !== null} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer cet utilisateur ?</DialogTitle>
            <DialogDescription>
              Cette action est irréversible. Toutes les données liées seront perdues.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>
              {fr.common.cancel}
            </Button>
            <Button variant="destructive" onClick={handleDelete} loading={remove.isPending}>
              {fr.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
