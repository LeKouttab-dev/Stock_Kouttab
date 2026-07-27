import { Package, AlertTriangle, PackageX, BarChart3 } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { KpiCard } from '@/components/shared/KpiCard';
import { EmptyState } from '@/components/shared/EmptyState';
import { useStockStatistics } from '@/api/endpoints/stock';
import { formatDateTime, formatNumber } from '@/lib/format';
import { STATUS_EMOJIS } from '@/lib/constants';
import { CHART_COLORS } from '@/lib/chart-theme';
import { fr } from '@/lib/i18n/fr';

export function OverviewTab() {
  const { data: stats, isLoading } = useStockStatistics();

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  if (!stats) return <EmptyState title="Aucune donnée disponible" />;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={fr.dashboard.totalArticles}
          value={formatNumber(stats.total_articles)}
          icon={<Package className="h-6 w-6" />}
          variant="info"
        />
        <KpiCard
          label={fr.dashboard.totalQuantite}
          value={formatNumber(stats.total_quantite)}
          icon={<BarChart3 className="h-6 w-6" />}
        />
        <KpiCard
          label={fr.dashboard.articlesAlerte}
          value={formatNumber(stats.alertes_stock)}
          icon={<AlertTriangle className="h-6 w-6" />}
          variant="warning"
        />
        <KpiCard
          label={fr.dashboard.stockEpuise}
          value={formatNumber(stats.stock_epuise)}
          icon={<PackageX className="h-6 w-6" />}
          variant="danger"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{fr.dashboard.repartitionCategorie}</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.stats_par_categorie.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={stats.stats_par_categorie}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="categorie" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} name="Nb articles" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="Aucune catégorie" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">🍔 {fr.dashboard.detailNourriture}</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.stats_nourriture_sous_categories.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={stats.stats_nourriture_sous_categories}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="sous_categorie" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill={CHART_COLORS[2]} radius={[4, 4, 0, 0]} name="Nb articles" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="Aucune sous-catégorie de Nourriture" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">🕐 {fr.dashboard.dernieresActivites}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {stats.dernieres_modifs && stats.dernieres_modifs.length > 0 ? (
            stats.dernieres_modifs.slice(0, 5).map((mod, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 rounded-md border bg-muted/20 px-3 py-2 text-sm"
              >
                <span aria-hidden>{STATUS_EMOJIS[mod.status] ?? '⚪'}</span>
                <p>
                  <strong>{formatDateTime(mod.date)}</strong> — {mod.prenom} {mod.nom} a{' '}
                  {mod.status.toLowerCase()} {formatNumber(mod.quantite_demandee)} unité(s) pour{' '}
                  <strong>{mod.article}</strong> ({mod.categorie})
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">Aucune activité récente.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
