import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useProfile, useUpdateProfile } from '@/api/endpoints/auth';
import { profileSchema, type ProfileFormValues } from '@/lib/schemas/auth';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

/**
 * Formulaire de profil, RIB compris.
 *
 * Existait en double, à l'identique, dans `ProfilePage` et dans l'onglet
 * « Profil » de `MyExpensesPage` — un champ ajouté d'un côté manquait de
 * l'autre. Les deux écrans consomment désormais ce composant.
 */
export function ProfileForm() {
  const { data: profile, isLoading } = useProfile();
  const update = useUpdateProfile();
  const toast = useToast();

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    values: profile
      ? {
          nom: profile.nom,
          prenom: profile.prenom,
          email: profile.email,
          telephone: profile.telephone ?? '',
          rib: profile.rib ?? '',
        }
      : undefined,
  });

  if (isLoading) return <LoadingSpinner fullPage />;

  const onSubmit = (values: ProfileFormValues) => {
    update.mutate(values, { onSuccess: () => toast.success(fr.expenses.profilUpdated) });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{fr.expenses.informationsRemboursement}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4 md:grid-cols-2">
          <div>
            <Label required>{fr.auth.nom}</Label>
            <Input {...form.register('nom')} />
          </div>
          <div>
            <Label required>{fr.auth.prenom}</Label>
            <Input {...form.register('prenom')} />
          </div>
          <div>
            <Label required>{fr.auth.email}</Label>
            <Input type="email" {...form.register('email')} />
          </div>
          <div>
            <Label>{fr.auth.telephone}</Label>
            <Input type="tel" {...form.register('telephone')} />
          </div>
          <div className="md:col-span-2">
            <Label>{fr.expenses.iban}</Label>
            <Input placeholder="FR76 …" {...form.register('rib')} />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" loading={update.isPending}>
              {fr.common.update}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
