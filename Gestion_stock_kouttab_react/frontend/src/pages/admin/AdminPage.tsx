import { useNavigate } from 'react-router-dom';
import { Database, Mail, Settings, Trash2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { useAuth } from '@/hooks/useAuth';
import { ACTIONS } from '@/lib/auth';
import {
  useCreateInvitation,
  useDeleteInvitation,
  useInvitations,
} from '@/api/endpoints/invitations';
import { useToast } from '@/hooks/useToast';
import { formatDateTime } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { PendingUsersSection } from './PendingUsersSection';
import { UsersManagementSection } from './UsersManagementSection';
import { PendingStockModsSection } from './PendingStockModsSection';
import { AddItemSection } from './AddItemSection';
import { ImportCsvSection } from './ImportCsvSection';
import { CategoriesManagementSection } from './CategoriesManagementSection';
import { SubCategoriesManagementSection } from './SubCategoriesManagementSection';
import { AnnuaireSection } from './AnnuaireSection';
import { ExpenseCategoriesManagementSection } from './ExpenseCategoriesManagementSection';
import { PolesManagementSection } from './PolesManagementSection';
import { EventsManagementSection } from './EventsManagementSection';
import { OutboundEmailsSection } from './OutboundEmailsSection';

const invitationFormSchema = z.object({
  email: z.string().email('Email invalide'),
});

type InvitationFormValues = z.infer<typeof invitationFormSchema>;

export function AdminPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const navigateToDatabase = () => navigate('/admin/database');
  const isSuperAdmin = can(ACTIONS.ADMIN_VALIDATE_USERS);
  const isStockAdmin = can(ACTIONS.STOCK_CRUD);
  const canImportCsv = can(ACTIONS.ADMIN_IMPORT_CSV);
  const canManagePoles = can(ACTIONS.POLES_MANAGE);
  const canManageEvents = can(ACTIONS.EVENTS_MANAGE);
  const canSuperviseOutbox = can(ACTIONS.COMPTA_RESEND_EMAIL);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Settings className="h-6 w-6" aria-hidden />
          {fr.admin.title}
        </h1>
        <p className="text-sm text-muted-foreground">
          Gestion des utilisateurs, des modifications de stock et des données.
        </p>
      </div>

      {isSuperAdmin && (
        <>
          <PendingUsersSection />
          <UsersManagementSection />
          <InvitationsSection />
          <Card>
            <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <Database className="h-6 w-6 text-primary" />
                <div>
                  <p className="font-semibold">{fr.admin.databaseTitle}</p>
                  <p className="text-sm text-muted-foreground">
                    Export ZIP, import CSV, diagnostic.
                  </p>
                </div>
              </div>
              <Button variant="outline" onClick={() => navigateToDatabase()}>
                Ouvrir
              </Button>
            </CardContent>
          </Card>
        </>
      )}

      {isStockAdmin && (
        <>
          <PendingStockModsSection />
          <AddItemSection />
          {canImportCsv && <ImportCsvSection />}
          <div className="grid gap-4 lg:grid-cols-2">
            <CategoriesManagementSection />
            <SubCategoriesManagementSection />
          </div>
        </>
      )}

      {/* Référentiels comptables : ils alimentent le nom des pièces envoyées
          au comptable, d'où leur place à côté de la gestion des données. */}
      {(canManagePoles || canManageEvents) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {canManagePoles && <PolesManagementSection />}
          {/* Les categories suivent les poles : elles remplacent l'evenement
              sous les poles qui n'en attendent pas. */}
          {canManagePoles && <ExpenseCategoriesManagementSection />}
          {canManageEvents && <EventsManagementSection />}
        </div>
      )}

      {/* Annuaire : la comptabilité y a accès, la gestion des comptes non. */}
      {canSuperviseOutbox && <AnnuaireSection />}

      {canSuperviseOutbox && <OutboundEmailsSection />}

      {!isSuperAdmin &&
        !isStockAdmin &&
        !canManagePoles &&
        !canManageEvents &&
        !canSuperviseOutbox && (
          <EmptyState
            title="Aucune section accessible"
            description="Votre rôle ne donne pas accès aux sections d'administration."
          />
        )}
    </div>
  );
}

function InvitationsSection() {
  const { data: invitations = [], isLoading } = useInvitations();
  const create = useCreateInvitation();
  const remove = useDeleteInvitation();
  const toast = useToast();

  const form = useForm<InvitationFormValues>({
    resolver: zodResolver(invitationFormSchema),
    defaultValues: { email: '' },
  });

  const onSubmit = (values: InvitationFormValues) => {
    create.mutate(
      { email: values.email },
      {
        onSuccess: () => {
          toast.success('Invitation envoyée par email');
          form.reset();
        },
      },
    );
  };

  const onRevoke = (id: number) => {
    if (!confirm('Révoquer cette invitation ?')) return;
    remove.mutate(id, { onSuccess: () => toast.success('Invitation révoquée') });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{fr.admin.inviterAdmin}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[220px]">
            <Label required>{fr.admin.emailInvite}</Label>
            <Input
              type="email"
              hasError={Boolean(form.formState.errors.email)}
              {...form.register('email')}
            />
            {form.formState.errors.email && (
              <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
            )}
          </div>
          <Button type="submit" loading={create.isPending}>
            <Mail className="h-4 w-4" />
            {fr.admin.envoyerInvitation}
          </Button>
        </form>

        {isLoading ? (
          <Skeleton className="h-32" />
        ) : invitations.length === 0 ? (
          <EmptyState title="Aucune invitation." />
        ) : (
          <ul className="space-y-2">
            {invitations.map((inv) => {
              const expired = new Date(inv.expires_at).getTime() < Date.now();
              const status = inv.used ? 'Utilisée' : expired ? 'Expirée' : 'Active';
              return (
                <li
                  key={inv.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/10 px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium">{inv.email}</p>
                    <p className="text-xs text-muted-foreground">
                      Créée le {formatDateTime(inv.created_at)} — Expire le{' '}
                      {formatDateTime(inv.expires_at)} — Tentatives : {inv.attempts}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium">{status}</span>
                    {!inv.used && !expired && (
                      <Button size="icon" variant="ghost" onClick={() => onRevoke(inv.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
