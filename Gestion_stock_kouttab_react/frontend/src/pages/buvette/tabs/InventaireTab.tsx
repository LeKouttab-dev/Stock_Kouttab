import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Banknote,
  Check,
  ClipboardList,
  FileSpreadsheet,
  Minus,
  Package,
  PackagePlus,
  Plus,
  TrendingDown,
  X,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
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
import { KpiCard } from '@/components/shared/KpiCard';
import { PeriodePreset } from '@/components/shared/PeriodePreset';
import { usePeriode } from '@/hooks/usePeriode';
import {
  paramsExportInventaires,
  useAbandonnerInventaire,
  useDemarrerInventaire,
  useEnregistrerComptage,
  useInventaire,
  useInventaireEnCours,
  useInventaireEspeces,
  useInventaires,
  useTelechargerExcel,
  useTerminerInventaire,
  useValiderStockInventaire,
} from '@/api/endpoints/buvette';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import { ACTIONS } from '@/lib/auth';
import {
  CLASSES_ECART,
  bornerQuantite,
  formatDateHeureParis,
  formatEcart,
  formatEcartUnites,
  jourParis,
  libelleDernierComptage,
  libelleEcartEspeces,
  lireEuros,
  lireQuantite,
  nomExportInventaires,
  QUANTITE_MAX,
  recapComptage,
  tonEcart,
} from '@/lib/buvette';
import { formatCents, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { eurosToCents } from '@/lib/money';
import { cn } from '@/lib/utils';
import type { Inventaire, InventaireLigne, InventaireStatut } from '@/types/api';
import { VentesEspeces } from '../VentesEspeces';

/** Délai d'enregistrement du brouillon après la dernière saisie. */
const DELAI_ENREGISTREMENT_MS = 800;

const t = fr.buvette.inventaire;

const VARIANTES_STATUT: Record<InventaireStatut, 'warning' | 'secondary' | 'success'> = {
  en_cours: 'warning',
  stock_valide: 'secondary',
  termine: 'success',
};

const ETAPE_PAR_STATUT: Record<InventaireStatut, 1 | 2 | 3> = {
  en_cours: 1,
  stock_valide: 2,
  termine: 3,
};

function classeEcartUnites(ecart: number): string {
  if (ecart === 0) return 'text-sage-700';
  return ecart < 0 ? 'text-red-700' : 'text-orange-600';
}

function nomCategorie(categorie: string | null): string | null {
  if (!categorie) return null;
  const onglets = fr.buvette.onglets as Record<string, string>;
  return onglets[categorie] ?? categorie;
}

function Vignette({ ligne }: { ligne: Pick<InventaireLigne, 'image_url' | 'emoji' | 'nom'> }) {
  return ligne.image_url ? (
    <img
      src={ligne.image_url}
      alt=""
      className="h-12 w-12 shrink-0 rounded-md object-cover"
      loading="lazy"
    />
  ) : (
    <span
      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-muted/40 text-3xl"
      aria-hidden
    >
      {ligne.emoji || '📦'}
    </span>
  );
}

function EcartEspeces({ cents, testId }: { cents: number; testId?: string }) {
  const ton = tonEcart(cents);
  return (
    <span data-testid={testId} data-ton={ton} className={cn('font-semibold', CLASSES_ECART[ton])}>
      {libelleEcartEspeces(cents)}
    </span>
  );
}

function IndicateurEtapes({ etape }: { etape: 1 | 2 | 3 }) {
  const etapes = [t.etapes.stock, t.etapes.especes, t.etapes.rapport];
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Étapes de l’inventaire">
      {etapes.map((nom, i) => {
        const n = i + 1;
        const faite = n < etape;
        const active = n === etape;
        return (
          <li
            key={nom}
            aria-current={active ? 'step' : undefined}
            className={cn(
              'flex items-center gap-2 rounded-full border px-3 py-1 text-sm',
              active && 'border-forest bg-forest text-white',
              faite && 'border-sage-300 bg-sage-200 text-forest-800',
              !active && !faite && 'border-border text-muted-foreground',
            )}
          >
            <span className="font-semibold">{faite ? <Check className="h-4 w-4" /> : n}</span>
            {nom}
          </li>
        );
      })}
    </ol>
  );
}

interface ConfirmationProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  titre: string;
  texte: string;
  libelle: string;
  onConfirmer: () => void;
  loading?: boolean;
  destructive?: boolean;
}

function Confirmation({
  open,
  onOpenChange,
  titre,
  texte,
  libelle,
  onConfirmer,
  loading,
  destructive,
}: ConfirmationProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titre}</DialogTitle>
          <DialogDescription>{texte}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t.annuler}
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'primary'}
            onClick={onConfirmer}
            loading={loading}
          >
            {libelle}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---- Compteur tactile ------------------------------------------------------ */

interface CompteurProps {
  nom: string;
  valeur: number;
  onChange: (n: number) => void;
}

function Compteur({ nom, valeur, onChange }: CompteurProps) {
  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant="outline"
        className="h-12 w-12 shrink-0 p-0"
        aria-label={t.retirerUn(nom)}
        disabled={valeur <= 0}
        onClick={() => onChange(Math.max(0, valeur - 1))}
      >
        <Minus className="h-5 w-5" />
      </Button>
      <Input
        aria-label={t.quantiteComptee(nom)}
        inputMode="numeric"
        autoComplete="off"
        value={String(valeur)}
        onFocus={(e) => e.target.select()}
        onChange={(e) => onChange(lireQuantite(e.target.value))}
        className="h-12 w-20 text-center text-lg font-semibold"
      />
      <Button
        type="button"
        variant="outline"
        className="h-12 w-12 shrink-0 p-0"
        aria-label={t.ajouterUn(nom)}
        disabled={valeur >= QUANTITE_MAX}
        onClick={() => onChange(bornerQuantite(valeur + 1))}
      >
        <Plus className="h-5 w-5" />
      </Button>
    </div>
  );
}

/* ---- Étape 1 : stock ------------------------------------------------------- */

function EtapeStock({ inv, onAbandon }: { inv: Inventaire; onAbandon: () => void }) {
  const toast = useToast();
  const { mutateAsync: enregistrerBrouillon } = useEnregistrerComptage();
  const valider = useValiderStockInventaire();
  const abandonner = useAbandonnerInventaire();

  const [comptes, setComptes] = useState<Record<number, number>>(() =>
    Object.fromEntries(inv.lignes.map((l) => [l.id, l.quantite_comptee])),
  );
  const comptesRef = useRef(comptes);
  const aEnvoyer = useRef<Set<number>>(new Set());
  const minuterie = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [etat, setEtat] = useState<'repos' | 'attente' | 'enregistre'>('repos');
  const [vue, setVue] = useState<'comptage' | 'recap'>('comptage');
  const [confirmerValidation, setConfirmerValidation] = useState(false);
  const [confirmerAbandon, setConfirmerAbandon] = useState(false);

  const envoyer = useCallback(async () => {
    if (minuterie.current) {
      clearTimeout(minuterie.current);
      minuterie.current = null;
    }
    if (aEnvoyer.current.size === 0) return;
    const lignes = [...aEnvoyer.current].map((id) => ({
      id,
      quantite_comptee: comptesRef.current[id] ?? 0,
    }));
    aEnvoyer.current = new Set();
    try {
      await enregistrerBrouillon({ id: inv.id, lignes });
      if (aEnvoyer.current.size === 0) setEtat('enregistre');
    } catch (e) {
      lignes.forEach((l) => aEnvoyer.current.add(l.id));
      setEtat('repos');
      throw e;
    }
  }, [enregistrerBrouillon, inv.id]);

  // En quittant l'écran, la dernière saisie part quand même.
  const envoyerRef = useRef(envoyer);
  envoyerRef.current = envoyer;
  useEffect(
    () => () => {
      if (aEnvoyer.current.size > 0) void envoyerRef.current().catch(() => undefined);
    },
    [],
  );

  const changer = (id: number, n: number) => {
    const suivant = { ...comptesRef.current, [id]: bornerQuantite(n) };
    comptesRef.current = suivant;
    setComptes(suivant);
    aEnvoyer.current.add(id);
    setEtat('attente');
    if (minuterie.current) clearTimeout(minuterie.current);
    minuterie.current = setTimeout(() => {
      void envoyer().catch(() => undefined);
    }, DELAI_ENREGISTREMENT_MS);
  };

  const voirEcarts = async () => {
    try {
      await envoyer();
      setVue('recap');
    } catch {
      // l'échec est déjà signalé par un toast
    }
  };

  const validerStock = async () => {
    try {
      await envoyer();
    } catch {
      return;
    }
    valider.mutate(inv.id, {
      onSuccess: () => {
        setConfirmerValidation(false);
        toast.success(t.stockValide);
      },
    });
  };

  const abandon = () => {
    if (minuterie.current) clearTimeout(minuterie.current);
    aEnvoyer.current = new Set();
    abandonner.mutate(inv.id, {
      onSuccess: () => {
        setConfirmerAbandon(false);
        toast.success(t.abandonne);
        onAbandon();
      },
    });
  };

  const recap = recapComptage(inv.lignes, comptes);

  return (
    <div className="space-y-5">
      {vue === 'comptage' ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">{t.comptageAide}</p>
            <p
              className="text-xs text-muted-foreground"
              aria-live="polite"
              data-testid="etat-brouillon"
            >
              {etat === 'attente' && t.enregistrement}
              {etat === 'enregistre' && (
                <span className="inline-flex items-center gap-1 text-sage-700">
                  <Check className="h-3.5 w-3.5" aria-hidden />
                  {t.enregistre}
                </span>
              )}
            </p>
          </div>

          {inv.lignes.length === 0 ? (
            <EmptyState title={t.aucunProduit} />
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {inv.lignes.map((l) => {
                const categorie = nomCategorie(l.categorie);
                return (
                  <li
                    key={l.id}
                    className="flex flex-wrap items-center justify-between gap-3 p-3"
                    data-testid={`ligne-${l.id}`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <Vignette ligne={l} />
                      <div className="min-w-0">
                        <p className="truncate font-medium">{l.nom}</p>
                        <p className="text-xs text-muted-foreground">
                          {categorie && <span>{categorie} · </span>}
                          {l.stock_actuel === null
                            ? t.produitSupprime
                            : t.stockEnBase(l.stock_actuel)}
                        </p>
                      </div>
                    </div>
                    <Compteur
                      nom={l.nom}
                      valeur={comptes[l.id] ?? 0}
                      onChange={(n) => changer(l.id, n)}
                    />
                  </li>
                );
              })}
            </ul>
          )}

          <div className="flex flex-wrap justify-between gap-2">
            <Button variant="ghost" onClick={() => setConfirmerAbandon(true)}>
              {t.abandonner}
            </Button>
            <Button onClick={() => void voirEcarts()} disabled={inv.lignes.length === 0}>
              {t.voirEcarts}
            </Button>
          </div>
        </>
      ) : (
        <>
          <h3 className="font-serif text-lg font-semibold text-forest">{t.recapTitre}</h3>
          {recap.ecarts.length === 0 ? (
            <p className="text-sm text-sage-700">{t.aucunEcart}</p>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <KpiCard
                  label={t.nbEcarts(recap.ecarts.length)}
                  value={formatEcartUnites(recap.ecartUnites)}
                  hint={t.unites(formatEcartUnites(recap.ecartUnites))}
                  icon={<Package className="h-6 w-6" />}
                  variant="info"
                />
                <KpiCard
                  label={t.totalEcart}
                  value={<span data-testid="recap-valeur">{formatEcart(recap.valeurCents)}</span>}
                  icon={<ClipboardList className="h-6 w-6" />}
                />
                <KpiCard
                  label={t.perteEstimee}
                  value={<span data-testid="recap-perte">{formatCents(recap.perteCents)}</span>}
                  icon={<TrendingDown className="h-6 w-6" />}
                  variant={recap.perteCents > 0 ? 'danger' : 'success'}
                />
              </div>
              <div className="overflow-x-auto rounded-md border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t.produit}</TableHead>
                      <TableHead className="text-right">{t.stockBase}</TableHead>
                      <TableHead className="text-right">{t.compte}</TableHead>
                      <TableHead className="text-right">{t.ecart}</TableHead>
                      <TableHead className="text-right">{t.valeur}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recap.ecarts.map((e) => (
                      <TableRow key={e.id} data-testid={`recap-${e.id}`}>
                        <TableCell>
                          <span aria-hidden>{e.emoji || '📦'}</span> {e.nom}
                        </TableCell>
                        <TableCell className="text-right">{e.stock}</TableCell>
                        <TableCell className="text-right">{e.compte}</TableCell>
                        <TableCell
                          className={cn('text-right font-semibold', classeEcartUnites(e.ecart))}
                        >
                          {formatEcartUnites(e.ecart)}
                        </TableCell>
                        <TableCell className="text-right">{formatEcart(e.valeur_cents)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
          <div className="flex flex-wrap justify-between gap-2">
            <Button variant="outline" onClick={() => setVue('comptage')}>
              {t.retourComptage}
            </Button>
            <Button onClick={() => setConfirmerValidation(true)}>
              <Check className="h-4 w-4" />
              {t.validerStock}
            </Button>
          </div>
        </>
      )}

      <Confirmation
        open={confirmerValidation}
        onOpenChange={setConfirmerValidation}
        titre={t.validerTitre}
        texte={t.validerTexte}
        libelle={t.validerConfirmer}
        onConfirmer={() => void validerStock()}
        loading={valider.isPending}
      />
      <Confirmation
        open={confirmerAbandon}
        onOpenChange={setConfirmerAbandon}
        titre={t.abandonTitre}
        texte={t.abandonTexte}
        libelle={t.abandonConfirmer}
        onConfirmer={abandon}
        loading={abandonner.isPending}
        destructive
      />
    </div>
  );
}

/* ---- Étape 2 : espèces ----------------------------------------------------- */

function EtapeEspeces({ inv }: { inv: Inventaire }) {
  const toast = useToast();
  const terminer = useTerminerInventaire();
  const [debut, setDebut] = useState('');
  const [saisie, setSaisie] = useState('');
  const [commentaire, setCommentaire] = useState('');

  const especes = useInventaireEspeces(inv.id, debut || null);
  // Une fois la date choisie, le champ reste affiché quelle que soit la réponse.
  const premier = debut !== '' || (especes.data?.premier_inventaire ?? false);
  const pret = !!especes.data && (!premier || debut !== '');

  const euros = lireEuros(saisie);
  const saisieInvalide = saisie.trim() !== '' && euros === null;
  const compteCents = euros === null ? null : eurosToCents(euros);
  const attendu = pret && especes.data ? especes.data.attendu_cents : null;
  const ecartCents = compteCents !== null && attendu !== null ? compteCents - attendu : null;

  const finir = () => {
    if (compteCents === null || !pret) return;
    terminer.mutate(
      {
        id: inv.id,
        especes_comptees_cents: compteCents,
        commentaire: commentaire.trim() || null,
        debut: premier ? debut : null,
      },
      { onSuccess: () => toast.success(t.termine) },
    );
  };

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">{t.especesAide}</p>

      {premier && (
        <div className="space-y-1">
          <p className="text-sm">{t.premierInventaire}</p>
          <Label htmlFor="inventaire-debut-especes">{t.dateDebut}</Label>
          <Input
            id="inventaire-debut-especes"
            type="date"
            required
            value={debut}
            onChange={(e) => setDebut(e.target.value)}
            className="w-44"
          />
        </div>
      )}

      {especes.isError ? (
        <ErrorAlert title={t.erreur} error={especes.error} />
      ) : !especes.data ? (
        <Skeleton className="h-32" />
      ) : !pret ? (
        <p className="text-sm text-muted-foreground">{t.choisirDate}</p>
      ) : (
        <>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t.attendu}
            </p>
            <p
              className="font-serif text-2xl font-bold text-forest"
              data-testid="especes-attendues"
            >
              {formatCents(especes.data.attendu_cents)}
            </p>
            <p className="text-xs text-muted-foreground">
              {t.nbVentes(especes.data.nb_ventes)}
              {especes.data.periode_debut &&
                `, ${(
                  libelleDernierComptage(especes.data.dernier_comptage, t) ??
                  t.periode(formatDateHeureParis(especes.data.periode_debut))
                ).toLowerCase()}`}
            </p>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold">{t.ventesTitre}</h3>
            <VentesEspeces ventes={especes.data.ventes} libelles={t} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="inventaire-especes">{t.especesComptees}</Label>
              <Input
                id="inventaire-especes"
                inputMode="decimal"
                autoComplete="off"
                placeholder="0,00"
                value={saisie}
                hasError={saisieInvalide}
                aria-invalid={saisieInvalide}
                onChange={(e) => setSaisie(e.target.value)}
              />
              {saisieInvalide && <p className="text-xs text-destructive">{t.montantInvalide}</p>}
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">{t.ecartEspeces}</p>
              <p className="flex h-10 items-center text-lg">
                {ecartCents === null ? (
                  <span className="text-muted-foreground">…</span>
                ) : (
                  <EcartEspeces cents={ecartCents} testId="ecart-especes" />
                )}
              </p>
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="inventaire-commentaire">{t.commentaire}</Label>
            <Textarea
              id="inventaire-commentaire"
              rows={2}
              maxLength={1000}
              value={commentaire}
              onChange={(e) => setCommentaire(e.target.value)}
            />
          </div>

          <div className="flex justify-end">
            <Button onClick={finir} disabled={compteCents === null} loading={terminer.isPending}>
              <Banknote className="h-4 w-4" />
              {t.terminer}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/* ---- Étape 3 : rapport ----------------------------------------------------- */

function Rapport({ inv }: { inv: Inventaire }) {
  const toast = useToast();
  const telecharger = useTelechargerExcel();
  const r = inv.resume;
  // Total des réappros de la période ; absent des rapports antérieurs au suivi des achats.
  const achats = r.achats_cents ?? null;
  const ecarts = inv.lignes.filter((l) => l.ecart !== null && l.ecart !== 0);
  const date = formatDate(inv.termine_le ?? inv.debut_le);

  const exporter = () =>
    telecharger.mutate(
      {
        chemin: `/buvette/inventaires/${inv.id}/export.xlsx`,
        nomParDefaut: `inventaire-${inv.id}-${jourParis(inv.debut_le)}.xlsx`,
      },
      { onSuccess: (nom) => toast.success(t.exporte(nom)) },
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-serif text-lg font-semibold text-forest">{t.rapportTitre(date)}</h3>
          {inv.cree_par && (
            <p className="text-xs text-muted-foreground">
              {t.saisiPar} {inv.cree_par}
            </p>
          )}
        </div>
        <Button variant="outline" onClick={exporter} loading={telecharger.isPending}>
          <FileSpreadsheet className="h-4 w-4" />
          {t.exporter}
        </Button>
      </div>

      {inv.statut !== 'termine' && <p className="text-sm text-muted-foreground">{t.nonTermine}</p>}

      <div
        className={`grid gap-4 sm:grid-cols-2 ${achats === null ? 'lg:grid-cols-3' : 'lg:grid-cols-4'}`}
      >
        <KpiCard
          label={t.ecartsProduits}
          value={<span data-testid="rapport-nb-ecarts">{r.nb_ecarts}</span>}
          hint={`${t.unites(formatEcartUnites(r.ecart_unites))}, ${formatEcart(r.valeur_ecart_cents)}`}
          icon={<Package className="h-6 w-6" />}
          variant="info"
        />
        <KpiCard
          label={t.perteEstimee}
          value={<span data-testid="rapport-perte">{formatCents(r.perte_cents)}</span>}
          icon={<TrendingDown className="h-6 w-6" />}
          variant={r.perte_cents > 0 ? 'danger' : 'success'}
        />
        <KpiCard
          label={t.ecartEspeces}
          value={
            inv.ecart_especes_cents === null ? (
              '…'
            ) : (
              <EcartEspeces cents={inv.ecart_especes_cents} testId="rapport-ecart-especes" />
            )
          }
          hint={
            inv.especes_attendues_cents === null
              ? undefined
              : `${t.especesAttendues} ${formatCents(inv.especes_attendues_cents)}, ` +
                `${t.especesCompteesCourt.toLowerCase()} ${formatCents(inv.especes_comptees_cents ?? 0)}`
          }
          icon={<Banknote className="h-6 w-6" />}
        />
        {achats !== null && (
          <KpiCard
            label={t.achatsPeriode}
            value={<span data-testid="rapport-achats">{formatCents(achats)}</span>}
            icon={<PackagePlus className="h-6 w-6" />}
            variant="info"
          />
        )}
      </div>

      {inv.commentaire && <p className="text-sm italic">{inv.commentaire}</p>}

      <div className="space-y-2">
        <h4 className="text-sm font-semibold">{t.ecartsProduitsTitre}</h4>
        {ecarts.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t.aucunEcart}</p>
        ) : (
          <div className="overflow-x-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.produit}</TableHead>
                  <TableHead className="text-right">{t.stockBase}</TableHead>
                  <TableHead className="text-right">{t.compte}</TableHead>
                  <TableHead className="text-right">{t.ecart}</TableHead>
                  <TableHead className="text-right">{t.valeur}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ecarts.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell>
                      <span aria-hidden>{l.emoji || '📦'}</span> {l.nom}
                    </TableCell>
                    <TableCell className="text-right">{l.quantite_theorique ?? ''}</TableCell>
                    <TableCell className="text-right">{l.quantite_comptee}</TableCell>
                    <TableCell
                      className={cn('text-right font-semibold', classeEcartUnites(l.ecart ?? 0))}
                    >
                      {formatEcartUnites(l.ecart ?? 0)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatEcart(l.valeur_ecart_cents ?? 0)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---- Un inventaire ouvert -------------------------------------------------- */

function InventaireVue({
  id,
  canCrud,
  onFermer,
}: {
  id: number;
  canCrud: boolean;
  onFermer: () => void;
}) {
  const q = useInventaire(id);
  const inv = q.data;

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 space-y-0">
        {inv ? <IndicateurEtapes etape={ETAPE_PAR_STATUT[inv.statut]} /> : <span />}
        <Button variant="ghost" size="sm" onClick={onFermer}>
          <X className="h-4 w-4" />
          {t.fermer}
        </Button>
      </CardHeader>
      <CardContent>
        {q.isError ? (
          <ErrorAlert title={t.erreur} error={q.error} />
        ) : !inv ? (
          <Skeleton className="h-48" />
        ) : inv.statut === 'en_cours' && canCrud ? (
          <EtapeStock key={inv.id} inv={inv} onAbandon={onFermer} />
        ) : inv.statut === 'stock_valide' && canCrud ? (
          <EtapeEspeces key={inv.id} inv={inv} />
        ) : (
          <Rapport inv={inv} />
        )}
      </CardContent>
    </Card>
  );
}

/* ---- Historique ------------------------------------------------------------ */

function Historique({ onOuvrir }: { onOuvrir: (id: number) => void }) {
  const toast = useToast();
  const [periode, setPeriode] = usePeriode('mois');
  const { debut, fin } = periode;
  const historique = useInventaires({ debut, fin });
  const telecharger = useTelechargerExcel();
  const liste = historique.data ?? [];

  const exporter = () =>
    telecharger.mutate(
      {
        chemin: '/buvette/inventaires/export.xlsx',
        params: paramsExportInventaires({ debut, fin }),
        nomParDefaut: nomExportInventaires(debut, fin),
      },
      { onSuccess: (nom) => toast.success(t.exporte(nom)) },
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="font-serif text-lg font-semibold text-forest">{t.historique}</h2>
        <div className="flex flex-wrap items-end gap-3">
          <PeriodePreset id="inventaires" valeur={periode} onChange={setPeriode} />
          <Button variant="outline" onClick={exporter} loading={telecharger.isPending}>
            <FileSpreadsheet className="h-4 w-4" />
            {t.exporterHistorique}
          </Button>
        </div>
      </div>

      {historique.isError ? (
        <ErrorAlert title={t.erreur} error={historique.error} />
      ) : historique.isLoading ? (
        <Skeleton className="h-40" />
      ) : liste.length === 0 ? (
        <EmptyState title={t.historiqueVide} />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.date}</TableHead>
                  <TableHead>{t.statut}</TableHead>
                  <TableHead className="text-right">{t.nbEcartsCol}</TableHead>
                  <TableHead className="text-right">{t.valeurEcarts}</TableHead>
                  <TableHead className="text-right">{t.ecartEspeces}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {liste.map((i) => {
                  const date = formatDate(i.debut_le);
                  return (
                    <TableRow key={i.id} className="cursor-pointer" onClick={() => onOuvrir(i.id)}>
                      <TableCell className="whitespace-nowrap">
                        <Button
                          variant="link"
                          className="h-auto p-0"
                          aria-label={t.ouvrir(date)}
                          onClick={(e) => {
                            e.stopPropagation();
                            onOuvrir(i.id);
                          }}
                        >
                          {date}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Badge variant={VARIANTES_STATUT[i.statut]}>{t.statuts[i.statut]}</Badge>
                      </TableCell>
                      <TableCell className="text-right">{i.resume.nb_ecarts}</TableCell>
                      <TableCell className="text-right">
                        {formatEcart(i.resume.valeur_ecart_cents)}
                      </TableCell>
                      <TableCell className="text-right">
                        {i.ecart_especes_cents === null ? (
                          ''
                        ) : (
                          <EcartEspeces cents={i.ecart_especes_cents} />
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ---- Onglet ---------------------------------------------------------------- */

export function InventaireTab() {
  const { can } = useAuth();
  const canCrud = can(ACTIONS.BUVETTE_CRUD);
  const toast = useToast();
  const enCours = useInventaireEnCours();
  const demarrer = useDemarrerInventaire();
  const [selection, setSelection] = useState<number | null>(null);

  const courant = enCours.data ?? null;

  const lancer = () =>
    demarrer.mutate(undefined, {
      onSuccess: (inv) => {
        toast.success(t.demarre);
        setSelection(inv.id);
      },
    });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t.titre}</CardTitle>
          <CardDescription>{t.aide}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {enCours.isError ? (
            <ErrorAlert title={t.erreur} error={enCours.error} />
          ) : enCours.isLoading ? (
            <Skeleton className="h-10 w-64" />
          ) : courant ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm">{t.enCoursDepuis(formatDateHeureParis(courant.debut_le))}</p>
              {canCrud && selection !== courant.id && (
                <Button onClick={() => setSelection(courant.id)}>
                  <ClipboardList className="h-4 w-4" />
                  {t.reprendre}
                </Button>
              )}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              {canCrud ? (
                <Button onClick={lancer} loading={demarrer.isPending}>
                  <ClipboardList className="h-4 w-4" />
                  {t.demarrer}
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">{t.aucunEnCours}</p>
              )}
            </div>
          )}
          {!canCrud && <p className="text-xs text-muted-foreground">{t.lectureSeule}</p>}
        </CardContent>
      </Card>

      {selection !== null && (
        <InventaireVue
          key={selection}
          id={selection}
          canCrud={canCrud}
          onFermer={() => setSelection(null)}
        />
      )}

      <Historique onOuvrir={setSelection} />
    </div>
  );
}
