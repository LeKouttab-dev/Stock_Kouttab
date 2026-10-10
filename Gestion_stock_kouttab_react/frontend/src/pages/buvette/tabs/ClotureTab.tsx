import { useState } from 'react';
import { FileSpreadsheet, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { PeriodePreset } from '@/components/shared/PeriodePreset';
import { usePeriode } from '@/hooks/usePeriode';
import {
  paramsClotures,
  useClotureAttendu,
  useClotures,
  useCreateCloture,
  useTelechargerExcel,
} from '@/api/endpoints/buvette';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { ACTIONS } from '@/lib/auth';
import {
  CLASSES_ECART,
  formatDateHeureParis,
  formatEcart,
  jourIso,
  libelleDernierComptage,
  lireEuros,
  nomExportPeriode,
  tonEcart,
} from '@/lib/buvette';
import { formatCents } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { eurosToCents } from '@/lib/money';
import { cn } from '@/lib/utils';
import { VentesEspeces } from '../VentesEspeces';

const t = fr.buvette.cloture;

function Ecart({ cents, className }: { cents: number; className?: string }) {
  return (
    <span
      data-testid="ecart"
      data-ton={tonEcart(cents)}
      className={cn('font-semibold', CLASSES_ECART[tonEcart(cents)], className)}
    >
      {formatEcart(cents)}
    </span>
  );
}

/** Saisie d'une clôture : depuis le dernier comptage (clôture ou inventaire). */
function NouvelleCloture() {
  const { can } = useAuth();
  const canCrud = can(ACTIONS.BUVETTE_CRUD);
  const toast = useToast();

  const [debut, setDebut] = useState('');
  const [saisie, setSaisie] = useState('');
  const [commentaire, setCommentaire] = useState('');
  const [confirmation, setConfirmation] = useState(false);

  const attendu = useClotureAttendu(debut || null);
  const creer = useCreateCloture();

  // Une fois la date choisie, le champ reste affiché quelle que soit la réponse.
  const premier = debut !== '' || (attendu.data?.premier_comptage ?? false);
  const pret = !!attendu.data && (!premier || debut !== '');

  const euros = lireEuros(saisie);
  const saisieInvalide = saisie.trim() !== '' && euros === null;
  const compteCents = euros === null ? null : eurosToCents(euros);
  const attenduCents = pret && attendu.data ? attendu.data.attendu_cents : null;
  const ecartCents =
    compteCents !== null && attenduCents !== null ? compteCents - attenduCents : null;

  const cloturer = () => {
    if (compteCents === null || !pret) return;
    creer.mutate(
      {
        compte_cents: compteCents,
        commentaire: commentaire.trim() || null,
        debut: premier ? debut : null,
      },
      {
        onSuccess: () => {
          toast.success(t.cloturee);
          setSaisie('');
          setCommentaire('');
          setDebut('');
        },
        onSettled: () => setConfirmation(false),
      },
    );
  };

  const depuis = libelleDernierComptage(attendu.data?.dernier_comptage, t);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t.titre}</CardTitle>
        <CardDescription>{t.aide}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {depuis && (
          <p className="text-sm font-medium" data-testid="cloture-depuis">
            {depuis}
          </p>
        )}

        {premier && (
          <div className="space-y-1">
            <p className="text-sm">{t.premierComptage}</p>
            <Label htmlFor="cloture-debut">{t.dateDebut}</Label>
            <Input
              id="cloture-debut"
              type="date"
              required
              value={debut}
              max={jourIso()}
              onChange={(e) => setDebut(e.target.value)}
              className="w-44"
            />
          </div>
        )}

        {attendu.isError ? (
          <ErrorAlert title={t.erreur} error={attendu.error} />
        ) : !attendu.data ? (
          <Skeleton className="h-32" />
        ) : !pret ? (
          <p className="text-sm text-muted-foreground">{t.choisirDate}</p>
        ) : (
          <>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t.attendu}
              </p>
              <p className="font-serif text-2xl font-bold text-forest" data-testid="attendu">
                {formatCents(attendu.data.attendu_cents)}
              </p>
              <p className="text-xs text-muted-foreground">{t.nbVentes(attendu.data.nb_ventes)}</p>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold">{t.ventesTitre}</h3>
              <VentesEspeces ventes={attendu.data.ventes} libelles={t} />
            </div>

            {!canCrud ? (
              <p className="text-sm text-muted-foreground">{t.lectureSeule}</p>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="cloture-compte">{t.compte}</Label>
                    <Input
                      id="cloture-compte"
                      inputMode="decimal"
                      autoComplete="off"
                      placeholder="0,00"
                      value={saisie}
                      hasError={saisieInvalide}
                      aria-invalid={saisieInvalide}
                      onChange={(e) => setSaisie(e.target.value)}
                    />
                    {saisieInvalide && (
                      <p className="text-xs text-destructive">{t.montantInvalide}</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{t.ecart}</p>
                    <p className="flex h-10 items-center text-lg">
                      {ecartCents === null ? (
                        <span className="text-muted-foreground">…</span>
                      ) : (
                        <Ecart cents={ecartCents} />
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">{t.ecartAide}</p>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="cloture-commentaire">{t.commentaire}</Label>
                  <Textarea
                    id="cloture-commentaire"
                    rows={2}
                    maxLength={500}
                    value={commentaire}
                    onChange={(e) => setCommentaire(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Button
                    onClick={() => setConfirmation(true)}
                    disabled={compteCents === null || creer.isPending}
                  >
                    <Lock className="h-4 w-4" />
                    {t.cloturer}
                  </Button>
                  <p className="text-xs text-muted-foreground">{t.rappelVider}</p>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>

      <Dialog open={confirmation} onOpenChange={(o) => !creer.isPending && setConfirmation(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.confirmerTitre}</DialogTitle>
            <DialogDescription>
              {t.confirmerTexte(formatCents(compteCents ?? 0), formatCents(attenduCents ?? 0))}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmation(false)}>
              {t.annuler}
            </Button>
            <Button onClick={cloturer} loading={creer.isPending}>
              <Lock className="h-4 w-4" />
              {t.confirmer}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

/** Historique filtrable des clôtures, et son export Excel. */
function HistoriqueClotures() {
  const [periode, setPeriode] = usePeriode('mois');
  const { debut, fin } = periode;
  const filtres = { debut, fin };
  const historique = useClotures(filtres);
  const telecharger = useTelechargerExcel();
  const toast = useToast();

  const exporter = () =>
    telecharger.mutate(
      {
        chemin: '/buvette/clotures/export.xlsx',
        params: paramsClotures(filtres),
        nomParDefaut: nomExportPeriode('clotures', debut, fin),
      },
      { onSuccess: (nom) => toast.success(t.exporte(nom)) },
    );

  const clotures = historique.data ?? [];

  return (
    <div className="space-y-3">
      <h2 className="font-serif text-lg font-semibold text-forest">{t.historique}</h2>
      <div className="flex flex-wrap items-end gap-3">
        <PeriodePreset id="clotures" valeur={periode} onChange={setPeriode} />
        <Button variant="outline" onClick={exporter} loading={telecharger.isPending}>
          <FileSpreadsheet className="h-4 w-4" />
          {t.exporter}
        </Button>
      </div>

      {historique.isError ? (
        <ErrorAlert title={t.erreur} error={historique.error} />
      ) : historique.isLoading ? (
        <Skeleton className="h-40" />
      ) : clotures.length === 0 ? (
        <EmptyState title={t.historiqueVide} />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.periode}</TableHead>
                  <TableHead className="text-right">{t.ventesCol}</TableHead>
                  <TableHead className="text-right">{t.attendu}</TableHead>
                  <TableHead className="text-right">{t.compteCourt}</TableHead>
                  <TableHead className="text-right">{t.ecart}</TableHead>
                  <TableHead>{t.commentaireCourt}</TableHead>
                  <TableHead>{t.saisiPar}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {clotures.map((c) => (
                  <TableRow key={c.id} data-testid="cloture-ligne">
                    <TableCell className="whitespace-nowrap text-xs">
                      {t.periodeDe(
                        formatDateHeureParis(c.periode_debut),
                        formatDateHeureParis(c.periode_fin),
                      )}
                    </TableCell>
                    <TableCell className="text-right">{c.nb_ventes}</TableCell>
                    <TableCell className="text-right">{formatCents(c.attendu_cents)}</TableCell>
                    <TableCell className="text-right">{formatCents(c.compte_cents)}</TableCell>
                    <TableCell className="text-right">
                      <Ecart cents={c.ecart_cents} />
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                      {c.commentaire ?? ''}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {c.saisi_par ?? ''}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function ClotureTab() {
  return (
    <div className="space-y-6">
      <NouvelleCloture />
      <HistoriqueClotures />
    </div>
  );
}
