import { useState } from 'react';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { useClotureAttendu, useClotures, useCreateCloture } from '@/api/endpoints/buvette';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { ACTIONS } from '@/lib/auth';
import { CLASSES_ECART, formatEcart, jourIso, lireEuros, tonEcart } from '@/lib/buvette';
import { formatCents, formatDate, formatDateTime } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { eurosToCents } from '@/lib/money';
import { cn } from '@/lib/utils';
import type { Cloture } from '@/types/api';

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

/** Un jour déjà clôturé : on montre ce qui a été saisi, sans rien permettre de modifier. */
function ClotureFaite({ cloture }: { cloture: Cloture }) {
  const t = fr.buvette.cloture;
  return (
    <div className="space-y-3 rounded-md border border-border bg-muted/30 p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <Lock className="h-4 w-4" aria-hidden />
        {t.dejaCloture}
      </p>
      <dl className="grid gap-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">{t.attendu}</dt>
          <dd className="font-semibold">{formatCents(cloture.attendu_cents)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t.compteCourt}</dt>
          <dd className="font-semibold">{formatCents(cloture.compte_cents)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t.ecart}</dt>
          <dd>
            <Ecart cents={cloture.ecart_cents} />
          </dd>
        </div>
      </dl>
      {cloture.commentaire && <p className="text-sm italic">{cloture.commentaire}</p>}
      <p className="text-xs text-muted-foreground">
        {t.saisiPar} {cloture.saisi_par ?? '?'}, {formatDateTime(cloture.created_at)}
      </p>
    </div>
  );
}

export function ClotureTab() {
  const { can } = useAuth();
  const canCrud = can(ACTIONS.BUVETTE_CRUD);
  const toast = useToast();
  const t = fr.buvette.cloture;

  const [jour, setJour] = useState(jourIso());
  const [saisie, setSaisie] = useState('');
  const [commentaire, setCommentaire] = useState('');

  const attendu = useClotureAttendu(jour);
  const historique = useClotures(30);
  const creer = useCreateCloture();

  const euros = lireEuros(saisie);
  const saisieInvalide = saisie.trim() !== '' && euros === null;
  const compteCents = euros === null ? null : eurosToCents(euros);
  const ecartCents =
    compteCents !== null && attendu.data ? compteCents - attendu.data.attendu_cents : null;

  const changerJour = (v: string) => {
    if (!v) return;
    setJour(v);
    setSaisie('');
    setCommentaire('');
  };

  const cloturer = () => {
    if (compteCents === null) return;
    creer.mutate(
      { jour, compte_cents: compteCents, commentaire: commentaire.trim() || null },
      {
        onSuccess: () => {
          toast.success(t.cloturee);
          setSaisie('');
          setCommentaire('');
        },
      },
    );
  };

  const cloture = attendu.data?.cloture ?? null;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.titre}</CardTitle>
          <CardDescription>{t.aide}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1">
            <Label htmlFor="cloture-jour">{t.jour}</Label>
            <Input
              id="cloture-jour"
              type="date"
              value={jour}
              max={jourIso()}
              onChange={(e) => changerJour(e.target.value)}
              className="w-44"
            />
          </div>

          {attendu.isError ? (
            <ErrorAlert title={t.erreur} error={attendu.error} />
          ) : attendu.isLoading || !attendu.data ? (
            <Skeleton className="h-32" />
          ) : (
            <>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t.attendu}
                </p>
                <p className="font-serif text-2xl font-bold text-forest" data-testid="attendu">
                  {formatCents(attendu.data.attendu_cents)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t.nbVentes(attendu.data.nb_ventes_especes)}
                </p>
              </div>

              {cloture ? (
                <ClotureFaite cloture={cloture} />
              ) : !canCrud ? (
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
                  <Button
                    onClick={cloturer}
                    disabled={compteCents === null}
                    loading={creer.isPending}
                  >
                    <Lock className="h-4 w-4" />
                    {t.cloturer}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="font-serif text-lg font-semibold text-forest">{t.historique}</h2>
        {historique.isLoading ? (
          <Skeleton className="h-40" />
        ) : (historique.data ?? []).length === 0 ? (
          <EmptyState title={t.historiqueVide} />
        ) : (
          <Card>
            <CardContent className="overflow-x-auto p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.jour}</TableHead>
                    <TableHead className="text-right">{t.attendu}</TableHead>
                    <TableHead className="text-right">{t.compteCourt}</TableHead>
                    <TableHead className="text-right">{t.ecart}</TableHead>
                    <TableHead>{t.commentaireCourt}</TableHead>
                    <TableHead>{t.saisiPar}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(historique.data ?? []).map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="whitespace-nowrap">{formatDate(c.jour)}</TableCell>
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
    </div>
  );
}
