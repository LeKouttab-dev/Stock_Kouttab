import { useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Download, Trash2, Upload } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import {
  useDeleteRibDocument,
  useProfile,
  useUpdateProfile,
  useUploadRibDocument,
} from '@/api/endpoints/auth';
import { profileSchema, type ProfileFormValues } from '@/lib/schemas/auth';
import { useDownloadAttachment } from '@/hooks/useDownloadAttachment';
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

        {/* Hors du formulaire : le dépôt est immédiat et n'attend pas
            « Mettre à jour ». Imbriquer un envoi de fichier dans la soumission
            du profil obligerait à re-téléverser le RIB à chaque correction de
            numéro de téléphone. */}
        <RibDocument nom={profile?.rib_document_nom ?? null} />
      </CardContent>
    </Card>
  );
}

/**
 * Le RIB en document, à côté de l'IBAN saisi.
 *
 * L'IBAN sert au virement, le document sert de preuve — la comptabilité le
 * réclamait par messages privés faute de pouvoir le récupérer ici.
 */
function RibDocument({ nom }: { nom: string | null }) {
  const upload = useUploadRibDocument();
  const remove = useDeleteRibDocument();
  const toast = useToast();
  const { download, downloadingId } = useDownloadAttachment();
  const champ = useRef<HTMLInputElement>(null);

  const onChoisir = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fichier = e.target.files?.[0];
    // Réinitialisé tout de suite : sans cela, redéposer le même fichier après
    // une suppression ne déclenche aucun `change`.
    e.target.value = '';
    if (!fichier) return;
    upload.mutate(fichier, { onSuccess: () => toast.success(fr.expenses.ribDocumentEnvoye) });
  };

  return (
    <div className="mt-6 space-y-2 border-t pt-4">
      <Label>{fr.expenses.ribDocument}</Label>
      <p className="text-xs text-muted-foreground">{fr.expenses.ribDocumentAide}</p>

      <input
        ref={champ}
        type="file"
        accept="application/pdf,image/png,image/jpeg"
        className="hidden"
        onChange={onChoisir}
        data-testid="rib-document-input"
      />

      {nom ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button
            type="button"
            onClick={() => download('/users/me/rib-document', nom, 0)}
            disabled={downloadingId === 0}
            className="inline-flex items-center gap-1 text-primary hover:underline disabled:opacity-60"
          >
            <Download className="h-3.5 w-3.5" />
            {nom}
          </button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => champ.current?.click()}
            loading={upload.isPending}
          >
            {fr.expenses.ribDocumentRemplacer}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              remove.mutate(undefined, {
                onSuccess: () => toast.success(fr.expenses.ribDocumentSupprime),
              })
            }
            loading={remove.isPending}
          >
            <Trash2 className="mr-1 h-3.5 w-3.5" />
            {fr.expenses.ribDocumentSupprimer}
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm text-muted-foreground">{fr.expenses.ribDocumentAucun}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => champ.current?.click()}
            loading={upload.isPending}
          >
            <Upload className="mr-1 h-3.5 w-3.5" />
            {fr.expenses.ribDocumentDeposer}
          </Button>
        </div>
      )}
    </div>
  );
}
