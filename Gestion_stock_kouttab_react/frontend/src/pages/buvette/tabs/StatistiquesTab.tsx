import { useMemo, useState } from 'react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { KpiCard } from '@/components/shared/KpiCard';
import { useBuvetteStats } from '@/api/endpoints/buvette';
import { jourIso, periodeGlissante } from '@/lib/buvette';
import { CHART_AXIS, CHART_COLORS, CHART_GRID } from '@/lib/chart-theme';
import { formatCents, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

type Periode = '7' | '30' | 'perso';

const euros = (cents: number) => Math.round(cents) / 100;
const tooltipEuros = (v: number) => `${v.toFixed(2).replace('.', ',')} €`;

function libelleMoyen(moyen: string): string {
  return (fr.buvette.moyens as Record<string, string>)[moyen] ?? moyen;
}

export function StatistiquesTab() {
  const [periode, setPeriode] = useState<Periode>('30');
  const defaut30 = periodeGlissante(30);
  const [debutPerso, setDebutPerso] = useState(defaut30.debut);
  const [finPerso, setFinPerso] = useState(jourIso());

  const { debut, fin } =
    periode === 'perso' ? { debut: debutPerso, fin: finPerso } : periodeGlissante(Number(periode));

  const { data, isLoading, isError, error } = useBuvetteStats(debut, fin);
  const t = fr.buvette.stats;

  const series = useMemo(() => {
    if (!data) return null;
    return {
      jours: data.par_jour.map((j) => ({
        jour: formatDate(j.jour, 'dd/MM'),
        ca: euros(j.ca_cents),
        ventes: j.ventes,
      })),
      heures: data.par_heure.map((h) => ({ heure: `${h.heure} h`, ventes: h.ventes })),
      produits: data.par_produit.map((p) => ({ nom: p.nom, ca: euros(p.ca_cents) })),
      moyens: data.par_moyen
        .filter((m) => m.ca_cents > 0)
        .map((m) => ({ moyen: libelleMoyen(m.moyen), ca: euros(m.ca_cents) })),
      caTotal: data.par_jour.reduce((acc, j) => acc + j.ca_cents, 0),
      ventesTotal: data.par_jour.reduce((acc, j) => acc + j.ventes, 0),
    };
  }, [data]);

  const boutons: { v: Periode; label: string }[] = [
    { v: '7', label: t.jours7 },
    { v: '30', label: t.jours30 },
    { v: 'perso', label: t.personnalisee },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <p className="text-sm font-medium">{t.periode}</p>
          <div className="flex gap-1" role="group" aria-label={t.periode}>
            {boutons.map((b) => (
              <Button
                key={b.v}
                size="sm"
                variant={periode === b.v ? 'primary' : 'outline'}
                aria-pressed={periode === b.v}
                onClick={() => setPeriode(b.v)}
              >
                {b.label}
              </Button>
            ))}
          </div>
        </div>
        {periode === 'perso' && (
          <>
            <div className="space-y-1">
              <Label htmlFor="stats-du">{fr.buvette.paiements.du}</Label>
              <Input
                id="stats-du"
                type="date"
                value={debutPerso}
                max={finPerso}
                onChange={(e) => e.target.value && setDebutPerso(e.target.value)}
                className="w-40"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="stats-au">{fr.buvette.paiements.au}</Label>
              <Input
                id="stats-au"
                type="date"
                value={finPerso}
                min={debutPerso}
                onChange={(e) => e.target.value && setFinPerso(e.target.value)}
                className="w-40"
              />
            </div>
          </>
        )}
      </div>

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
                    <Tooltip formatter={(v: number) => [tooltipEuros(v), t.ca]} />
                    <Bar dataKey="ca" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
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
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
