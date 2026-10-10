import { useState } from 'react';
import { Coins, FileSpreadsheet, PackagePlus, ShoppingCart } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
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
  paramsReappros,
  useBuvetteProducts,
  useBuvetteReappros,
  useTelechargerExcel,
  type ReapprosFiltres,
} from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import { formatDateHeureParis } from '@/lib/buvette';
import { formatCents } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { cn } from '@/lib/utils';
import type { OrigineReappro } from '@/types/api';

const TOUS = 'tous';

const CLASSES_ORIGINE: Record<OrigineReappro, string> = {
  app: 'bg-forest-100 text-forest-800 border-forest-200',
  tablette: 'bg-terracotta-100 text-terracotta-800 border-terracotta-200',
};

function OrigineBadge({ origine }: { origine: OrigineReappro }) {
  return (
    <Badge variant="outline" className={cn('whitespace-nowrap', CLASSES_ORIGINE[origine])}>
      {fr.buvette.reappros.origines[origine]}
    </Badge>
  );
}

/** Historique des réapprovisionnements : app stock (avec prix) et tablette (sans prix). */
export function ReapprosTab() {
  const t = fr.buvette.reappros;
  const [periode, setPeriode] = usePeriode('mois');
  const { debut, fin } = periode;
  const [produit, setProduit] = useState<string>(TOUS);
  const [origine, setOrigine] = useState<OrigineReappro | typeof TOUS>(TOUS);

  const filtres: ReapprosFiltres = {
    debut,
    fin,
    productId: produit === TOUS ? null : Number(produit),
    origine: origine === TOUS ? null : origine,
  };
  const { data, isLoading, isError, error } = useBuvetteReappros(filtres);
  const produits = useBuvetteProducts().data ?? [];
  const telecharger = useTelechargerExcel();
  const toast = useToast();

  // Exactement les filtres affichés : le classeur reprend ce que l'écran montre.
  const exporter = () =>
    telecharger.mutate(
      {
        chemin: '/buvette/reapprovisionnements/export.xlsx',
        params: paramsReappros(filtres),
        nomParDefaut: `reapprovisionnements-${debut}_${fin}.xlsx`,
      },
      { onSuccess: (nom) => toast.success(t.exporte(nom)) },
    );

  const totaux = data?.totaux;
  const reappros = data?.reappros ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <PeriodePreset id="reappros" valeur={periode} onChange={setPeriode} />
        <div className="space-y-1">
          <Label htmlFor="reappros-produit">{t.produit}</Label>
          <Select value={produit} onValueChange={setProduit}>
            <SelectTrigger id="reappros-produit" className="w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUS}>{t.tousProduits}</SelectItem>
              {produits.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="reappros-origine">{t.origine}</Label>
          <Select
            value={origine}
            onValueChange={(v) => setOrigine(v as OrigineReappro | typeof TOUS)}
          >
            <SelectTrigger id="reappros-origine" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUS}>{t.toutesOrigines}</SelectItem>
              <SelectItem value="app">{t.origines.app}</SelectItem>
              <SelectItem value="tablette">{t.origines.tablette}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" onClick={exporter} loading={telecharger.isPending}>
          <FileSpreadsheet className="h-4 w-4" />
          {t.exporter}
        </Button>
      </div>

      {isError ? (
        <ErrorAlert title={t.erreur} error={error} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <KpiCard
              label={t.nb}
              value={<span data-testid="reappros-nb">{totaux ? totaux.nb : '…'}</span>}
              icon={<PackagePlus className="h-6 w-6" />}
              variant="info"
            />
            <KpiCard
              label={t.quantite}
              value={<span data-testid="reappros-quantite">{totaux ? totaux.quantite : '…'}</span>}
              icon={<ShoppingCart className="h-6 w-6" />}
              variant="success"
            />
            <KpiCard
              label={t.montant}
              value={
                <span data-testid="reappros-montant">
                  {totaux ? formatCents(totaux.montant_cents) : '…'}
                </span>
              }
              hint={t.montantAide}
              icon={<Coins className="h-6 w-6" />}
            />
          </div>

          {isLoading ? (
            <Skeleton className="h-72" />
          ) : reappros.length === 0 ? (
            <EmptyState title={t.vide} />
          ) : (
            <Card>
              <CardContent className="overflow-x-auto p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t.date}</TableHead>
                      <TableHead>{t.produit}</TableHead>
                      <TableHead className="text-right">{t.quantiteCol}</TableHead>
                      <TableHead className="text-right">{t.prixUnitaire}</TableHead>
                      <TableHead className="text-right">{t.total}</TableHead>
                      <TableHead>{t.origine}</TableHead>
                      <TableHead>{t.par}</TableHead>
                      <TableHead>{t.commentaire}</TableHead>
                      <TableHead className="text-right">{t.stock}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reappros.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="whitespace-nowrap text-xs">
                          {formatDateHeureParis(r.created_at)}
                        </TableCell>
                        <TableCell className="font-medium">{r.nom}</TableCell>
                        <TableCell className="text-right font-semibold">+{r.quantite}</TableCell>
                        <TableCell className="whitespace-nowrap text-right">
                          {r.prix_achat_unitaire_cents === null ? (
                            <span className="text-xs italic text-muted-foreground">
                              {t.nonRenseigne}
                            </span>
                          ) : (
                            formatCents(r.prix_achat_unitaire_cents)
                          )}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-right">
                          {r.total_cents === null ? '' : formatCents(r.total_cents)}
                        </TableCell>
                        <TableCell>
                          <OrigineBadge origine={r.origine} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {r.fait_par ?? ''}
                        </TableCell>
                        <TableCell className="max-w-xs text-sm text-muted-foreground">
                          {r.commentaire ?? ''}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-right text-sm">
                          {r.stock_avant} → {r.stock_apres}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
