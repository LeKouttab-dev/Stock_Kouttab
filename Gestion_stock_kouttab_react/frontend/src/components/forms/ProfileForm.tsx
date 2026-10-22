import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { CheckCircle2, Send } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useProfile, useTransmettreRib, useUpdateProfile } from '@/api/endpoints/auth';
import { profileSchema, type ProfileFormValues } from '@/lib/schemas/auth';
import { formatDate } from '@/lib/format';
import { ibanValide } from '@/lib/iban';
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
            <Button type="submit" loading={update.isPending}>
              {fr.common.update}
            </Button>
          </div>
        </form>

        {/* Hors du formulaire : l'envoi est immédiat et n'attend pas
            « Mettre à jour ». */}
        <Rib
          transmisLe={profile?.rib_transmis_le ?? null}
          ibanFin={profile?.rib_iban_fin ?? null}
        />
      </CardContent>
    </Card>
  );
}

/**
 * Le RIB : IBAN et relevé, envoyés ensemble au trésorier.
 *
 * Rien n'est conservé dans l'application — le serveur transmet par courriel et
 * ne garde que la date et la fin de l'IBAN. Une fois transmis, on n'affiche donc
 * que ce constat, et un bouton pour en envoyer un nouveau (changement de banque).
 */
function Rib({ transmisLe, ibanFin }: { transmisLe: string | null; ibanFin: string | null }) {
  const transmettre = useTransmettreRib();
  const toast = useToast();
  const [ouvert, setOuvert] = useState(!transmisLe);
  const [iban, setIban] = useState('');
  const [fichier, setFichier] = useState<File | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const envoyer = () => {
    if (!ibanValide(iban)) {
      setErreur(fr.expenses.ribIbanInvalide);
      return;
    }
    if (!fichier) {
      setErreur(fr.expenses.ribFichierRequis);
      return;
    }
    setErreur(null);
    transmettre.mutate(
      { iban, file: fichier },
      {
        onSuccess: () => {
          toast.success(fr.expenses.ribEnvoye);
          setIban('');
          setFichier(null);
          setOuvert(false);
        },
      },
    );
  };

  return (
    <div className="mt-6 space-y-3 border-t pt-4" data-testid="rib">
      <Label>{fr.expenses.ribTitre}</Label>
      {transmisLe && (
        <p className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          {fr.expenses.ribTransmisLe(formatDate(transmisLe), ibanFin)}
        </p>
      )}

      {ouvert ? (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">{fr.expenses.ribAide}</p>
          <div>
            <Label htmlFor="rib-iban">{fr.expenses.iban}</Label>
            <Input
              id="rib-iban"
              placeholder="FR76 …"
              autoComplete="off"
              value={iban}
              onChange={(e) => setIban(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="rib-fichier">{fr.expenses.ribDocument}</Label>
            <Input
              id="rib-fichier"
              type="file"
              // Mêmes formats que les justificatifs, HEIC compris : c'est le
              // format par défaut d'iOS, et le serveur convertit en PDF.
              accept=".pdf,.png,.jpg,.jpeg,.heic,.heif,.webp,application/pdf,image/*"
              onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
              data-testid="rib-document-input"
            />
          </div>
          {erreur && <p className="text-sm text-destructive">{erreur}</p>}
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={envoyer} loading={transmettre.isPending}>
              <Send className="mr-1 h-3.5 w-3.5" />
              {fr.expenses.ribEnvoyer}
            </Button>
            {transmisLe && (
              <Button type="button" variant="ghost" onClick={() => setOuvert(false)}>
                {fr.expenses.ribAnnuler}
              </Button>
            )}
          </div>
        </div>
      ) : (
        <Button type="button" variant="outline" size="sm" onClick={() => setOuvert(true)}>
          {fr.expenses.ribNouveau}
        </Button>
      )}
    </div>
  );
}
