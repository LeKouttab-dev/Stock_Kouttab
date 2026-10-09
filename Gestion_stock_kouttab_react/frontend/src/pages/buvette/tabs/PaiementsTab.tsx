import { Fragment, useState } from 'react';
import {
  Banknote,
  ChevronDown,
  ChevronRight,
  Coins,
  CreditCard,
  FileSpreadsheet,
  Link2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
import {
  paramsExportPaiements,
  useBuvettePaiements,
  useTelechargerExcel,
} from '@/api/endpoints/buvette';
import { useToast } from '@/hooks/useToast';
import { jourIso } from '@/lib/buvette';
import { formatCents, formatDateTime } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import { cn } from '@/lib/utils';
import type { MoyenPaiement, Paiement } from '@/types/api';

const TOUS = 'tous';

/** Une couleur par moyen : on les distingue d'un coup d'œil dans la liste. */
const CLASSES_MOYEN: Record<MoyenPaiement, string> = {
  carte: 'bg-forest-100 text-forest-800 border-forest-200',
  especes: 'bg-sage-200 text-forest-800 border-sage-300',
  helloasso: 'bg-terracotta-100 text-terracotta-800 border-terracotta-200',
};

export function MoyenBadge({ moyen }: { moyen: MoyenPaiement }) {
  return (
    <Badge variant="outline" className={cn('whitespace-nowrap', CLASSES_MOYEN[moyen])}>
      {fr.buvette.moyens[moyen]}
    </Badge>
  );
}

/** Le code SumUp sert au rapprochement avec le relevé ; la commande, avec HelloAsso. */
function reference(p: Paiement): string {
  if (p.moyen === 'helloasso' && p.helloasso_order_id !== null) {
    return fr.buvette.paiements.commande(p.helloasso_order_id);
  }
  return p.sumup_tx_code ?? '';
}

export function PaiementsTab() {
  const aujourdhui = jourIso();
  const [debut, setDebut] = useState(aujourdhui);
  const [fin, setFin] = useState(aujourdhui);
  const [moyen, setMoyen] = useState<MoyenPaiement | typeof TOUS>(TOUS);
  const [ouverts, setOuverts] = useState<Set<string>>(new Set());

  const filtres = { debut, fin, moyen: moyen === TOUS ? null : moyen };
  const { data, isLoading, isError, error } = useBuvettePaiements(filtres);
  const telecharger = useTelechargerExcel();
  const toast = useToast();

  // Exactement les filtres affichés : le classeur reprend ce que l'écran montre.
  const exporter = () =>
    telecharger.mutate(
      {
        chemin: '/buvette/paiements/export.xlsx',
        params: paramsExportPaiements(filtres),
        nomParDefaut: `paiements-${debut}_${fin}.xlsx`,
      },
      { onSuccess: (nom) => toast.success(fr.buvette.paiements.exporte(nom)) },
    );

  const basculer = (cle: string) =>
    setOuverts((prev) => {
      const suivant = new Set(prev);
      if (suivant.has(cle)) suivant.delete(cle);
      else suivant.add(cle);
      return suivant;
    });

  const t = fr.buvette.paiements;
  const totaux = data?.totaux;
  const paiements = data?.paiements ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="paiements-du">{t.du}</Label>
          <Input
            id="paiements-du"
            type="date"
            value={debut}
            max={fin}
            onChange={(e) => e.target.value && setDebut(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="paiements-au">{t.au}</Label>
          <Input
            id="paiements-au"
            type="date"
            value={fin}
            min={debut}
            onChange={(e) => e.target.value && setFin(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="paiements-moyen">{t.moyen}</Label>
          <Select value={moyen} onValueChange={(v) => setMoyen(v as MoyenPaiement | typeof TOUS)}>
            <SelectTrigger id="paiements-moyen" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUS}>{fr.buvette.moyens.tous}</SelectItem>
              <SelectItem value="carte">{fr.buvette.moyens.carte}</SelectItem>
              <SelectItem value="especes">{fr.buvette.moyens.especes}</SelectItem>
              <SelectItem value="helloasso">{fr.buvette.moyens.helloasso}</SelectItem>
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label={t.total}
              value={totaux ? formatCents(totaux.total_cents) : '…'}
              hint={totaux ? t.nbVentes(totaux.nb_ventes) : undefined}
              icon={<Coins className="h-6 w-6" />}
            />
            <KpiCard
              label={t.carte}
              value={totaux ? formatCents(totaux.carte_cents) : '…'}
              icon={<CreditCard className="h-6 w-6" />}
              variant="info"
            />
            <KpiCard
              label={t.especes}
              value={totaux ? formatCents(totaux.especes_cents) : '…'}
              icon={<Banknote className="h-6 w-6" />}
              variant="success"
            />
            <KpiCard
              label={t.helloasso}
              value={totaux ? formatCents(totaux.helloasso_cents) : '…'}
              icon={<Link2 className="h-6 w-6" />}
              variant="warning"
            />
          </div>

          {isLoading ? (
            <Skeleton className="h-72" />
          ) : paiements.length === 0 ? (
            <EmptyState title={t.vide} />
          ) : (
            <Card>
              <CardContent className="overflow-x-auto p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10" />
                      <TableHead>{t.date}</TableHead>
                      <TableHead>{t.moyenCol}</TableHead>
                      <TableHead className="text-right">{t.montant}</TableHead>
                      <TableHead>{t.reference}</TableHead>
                      <TableHead>{t.client}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paiements.map((p) => {
                      const ouvert = ouverts.has(p.cle);
                      return (
                        <Fragment key={p.cle}>
                          <TableRow className="cursor-pointer" onClick={() => basculer(p.cle)}>
                            <TableCell className="py-2">
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-expanded={ouvert}
                                aria-label={ouvert ? t.masquerDetail : t.afficherDetail}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  basculer(p.cle);
                                }}
                              >
                                {ouvert ? (
                                  <ChevronDown className="h-4 w-4" />
                                ) : (
                                  <ChevronRight className="h-4 w-4" />
                                )}
                              </Button>
                            </TableCell>
                            <TableCell className="whitespace-nowrap text-xs">
                              {formatDateTime(p.sold_at)}
                            </TableCell>
                            <TableCell>
                              <MoyenBadge moyen={p.moyen} />
                            </TableCell>
                            <TableCell className="text-right font-semibold">
                              {formatCents(p.total_cents)}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {reference(p)}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {p.client ?? ''}
                            </TableCell>
                          </TableRow>
                          {ouvert && (
                            <TableRow className="bg-muted/30 hover:bg-muted/30">
                              <TableCell />
                              <TableCell colSpan={5} className="py-3">
                                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                                  {t.detail}
                                </p>
                                <ul className="space-y-1 text-sm">
                                  {p.articles.map((a, i) => (
                                    <li
                                      key={`${a.nom}-${i}`}
                                      className="flex max-w-md justify-between gap-4"
                                    >
                                      <span>
                                        {a.quantite} × {a.nom}
                                      </span>
                                      <span className="font-medium">
                                        {formatCents(a.montant_cents)}
                                      </span>
                                    </li>
                                  ))}
                                </ul>
                              </TableCell>
                            </TableRow>
                          )}
                        </Fragment>
                      );
                    })}
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
