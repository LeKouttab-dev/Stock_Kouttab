import { useRef, useState } from 'react';
import { Smartphone, Upload } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  useCaisseAppVersion,
  usePublierCaisseApp,
  useRetirerCaisseApp,
} from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import { fr } from '@/lib/i18n/fr';

interface AppCaisseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Publication de l'application de la tablette de caisse.
 *
 * La tablette tourne en mode borne : personne n'y ouvre un magasin
 * d'applications, c'est elle qui vient chercher sa mise à jour — une minute
 * après le démarrage, puis toutes les demi-heures, et seulement au repos.
 *
 * Le numéro de version est saisi plutôt que déduit : le lire dans l'APK
 * supposerait de décoder le manifeste binaire d'Android. La tablette
 * n'installe que si ce numéro **dépasse** le sien.
 */
export function AppCaisseModal({ open, onOpenChange }: AppCaisseModalProps) {
  const { data: version } = useCaisseAppVersion(open);
  const publier = usePublierCaisseApp();
  const retirer = useRetirerCaisseApp();
  const champ = useRef<HTMLInputElement>(null);
  const [fichier, setFichier] = useState<File | null>(null);
  const [versionCode, setVersionCode] = useState('');
  const [versionName, setVersionName] = useState('');
  const toast = useToast();

  const envoyer = () => {
    if (!fichier || !versionCode) return;
    publier.mutate(
      { file: fichier, version_code: Number(versionCode), version_name: versionName.trim() },
      {
        onSuccess: () => {
          toast.success('Application publiée. Les tablettes se mettront à jour au repos.');
          setFichier(null);
          setVersionCode('');
          setVersionName('');
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Application de la tablette</DialogTitle>
          <DialogDescription>
            Publier une nouvelle version, que les tablettes installeront d&apos;elles-mêmes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {version ? (
            <Alert variant="info">
              <AlertDescription>
                Version servie : <strong>{version.version_name}</strong> (code{' '}
                {version.version_code}), {Math.round(version.taille / 1024 / 1024)} Mo, déposée le{' '}
                {new Date(version.depose_le).toLocaleDateString('fr-FR')}.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert>
              <AlertDescription>
                Aucune version publiée : les tablettes gardent celle qu&apos;elles exécutent.
              </AlertDescription>
            </Alert>
          )}

          <div className="space-y-1.5">
            <Label>Fichier APK</Label>
            <input
              ref={champ}
              type="file"
              accept=".apk,application/vnd.android.package-archive"
              className="hidden"
              onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" onClick={() => champ.current?.click()}>
                <Upload className="h-4 w-4" />
                Choisir l&apos;APK
              </Button>
              {fichier && (
                <span className="text-sm text-muted-foreground">
                  {fichier.name} — {Math.round(fichier.size / 1024 / 1024)} Mo
                </span>
              )}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="version_code" required>
                Numéro de version (versionCode)
              </Label>
              <Input
                id="version_code"
                type="number"
                min={1}
                value={versionCode}
                onChange={(e) => setVersionCode(e.target.value)}
                placeholder="3"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="version_name" required>
                Nom de version
              </Label>
              <Input
                id="version_name"
                value={versionName}
                onChange={(e) => setVersionName(e.target.value)}
                placeholder="0.3.0"
              />
            </div>
          </div>

          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <Smartphone className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
            La tablette vérifie au repos, une minute après le démarrage puis toutes les 30 minutes.
            Elle n&apos;installe que si le numéro dépasse le sien, et contrôle l&apos;empreinte du
            fichier avant de le faire.
          </p>
        </div>

        <DialogFooter>
          {version && (
            <Button
              type="button"
              variant="ghost"
              loading={retirer.isPending}
              onClick={() =>
                retirer.mutate(undefined, {
                  onSuccess: () => toast.success('Version retirée.'),
                })
              }
            >
              Retirer la version
            </Button>
          )}
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {fr.common.cancel}
          </Button>
          <Button
            type="button"
            loading={publier.isPending}
            disabled={!fichier || !versionCode || !versionName.trim()}
            onClick={envoyer}
          >
            Publier
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
