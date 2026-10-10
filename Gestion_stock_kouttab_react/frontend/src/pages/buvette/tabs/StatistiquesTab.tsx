import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { KpiCard } from '@/components/shared/KpiCard';
import { PeriodePreset } from '@/components/shared/PeriodePreset';
import { usePeriode } from '@/hooks/usePeriode';
import { useBuvetteStats } from '@/api/endpoints/buvette';
import { CHART_AXIS, CHART_COLORS, CHART_GRID } from '@/lib/chart-theme';
import { formatCents, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

const euros = (cents: number) => Math.round(cents) / 100;
const tooltipEuros = (v: number) => `${v.toFixed(2).replace('.', ',')} €`;

function libelleMoyen(moyen: string): string {
  return (fr.buvette.moyens as Record<string, string>)[moyen] ?? moyen;
}

export function StatistiquesTab() {
  const [periode, setPeriode] = usePeriode('mois');
  const { debut, fin } = periode;

  const { data, isLoading, isError, error } = useBuvetteStats(debut, fin);
  const t = fr.buvette.stats;

  const series = useMemo(() => {
    if (!data) return null;
    return {
      jours: data.par_jour.map((j) => ({
        jour: formatDate(j.jour, 'dd/MM'),
        ca: euros(j.ca_cents),
        net: euros(j.net_cents),
        ventes: j.ventes,
      })),
      heures: data.par_heure.map((h) => ({ heure: `${h.heure} h`, ventes: h.ventes })),
      produits: data.par_produit.map((p) => ({ nom: p.nom, ca: euros(p.ca_cents) })),
      moyens: data.par_moyen
        .filter((m) => m.ca_cents > 0)
        .map((m) => ({
          moyen: libelleMoyen(m.moyen),
          ca: euros(m.ca_cents),
          caCents: m.ca_cents,
          netCents: m.net_cents,
        })),
      // Montants calculés par le serveur (frais SumUp par transaction).
      caTotal: data.totaux.ca_cents,
      netTotal: data.totaux.net_cents,
      fraisTotal: data.totaux.frais_carte_cents,
      ventesTotal: data.totaux.ventes,
    };
  }, [data]);

  return (
    <div className="space-y-6">
      <PeriodePreset id="stats" valeur={periode} onChange={setPeriode} />

      {isError ? (
        <ErrorAlert title={t.erreur} error={error} />
      ) : isLoading || !series ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-72" />
          ))}
        </div>
      ) : series.ventesTotal === 0 ? (
        <EmptyState title={t.vide} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <KpiCard
              label={t.caTotal}
              value={formatCents(series.caTotal)}
              hint={fr.buvette.paiements.nbVentes(series.ventesTotal)}
            />
            <KpiCard
              label={t.caNet}
              value={<span data-testid="stats-ca-net">{formatCents(series.netTotal)}</span>}
              hint={t.caNetAide(formatCents(series.fraisTotal))}
              variant="success"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t.caParJour}</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={series.jours}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                    <XAxis dataKey="jour" tick={{ fontSize: 11, fill: CHART_AXIS }} />
                    <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} />
                    <Tooltip formatter={(v: number, nom: string) => [tooltipEuros(v), nom]} />
                    <Legend />
                    <Bar dataKey="ca" name={t.brut} fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="net" name={t.net} fill={CHART_COLORS[2]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t.ventesParHeure}</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={series.heures}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                    <XAxis dataKey="heure" tick={{ fontSize: 10, fill: CHART_AXIS }} interval={1} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: CHART_AXIS }} />
                    <Tooltip formatter={(v: number) => [v, t.ventes]} />
                    <Bar dataKey="ventes" fill={CHART_COLORS[2]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t.topProduits}</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer
                  width="100%"
                  height={Math.max(200, series.produits.length * 28 + 40)}
                >
                  <BarChart data={series.produits} layout="vertical" margin={{ left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: CHART_AXIS }} />
                    <YAxis
                      type="category"
                      dataKey="nom"
                      width={130}
                      tick={{ fontSize: 11, fill: CHART_AXIS }}
                    />
                    <Tooltip formatter={(v: number) => [tooltipEuros(v), t.ca]} />
                    <Bar dataKey="ca" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">{t.parMoyen}</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={series.moyens}
                      dataKey="ca"
                      nameKey="moyen"
                      innerRadius={50}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {series.moyens.map((m, i) => (
                        <Cell key={m.moyen} fill={CHART_COLORS[[0, 2, 3, 1][i % 4]]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => tooltipEuros(v)} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="mt-3 space-y-1 text-sm" data-testid="stats-par-moyen">
                  {series.moyens.map((m) => (
                    <li key={m.moyen} className="flex justify-between gap-4">
                      <span>{m.moyen}</span>
                      <span>
                        {t.brut} {formatCents(m.caCents)}, {t.net.toLowerCase()}{' '}
                        <span className="font-medium">{formatCents(m.netCents)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
