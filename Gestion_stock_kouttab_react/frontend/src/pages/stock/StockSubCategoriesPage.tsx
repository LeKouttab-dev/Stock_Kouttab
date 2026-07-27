import { useMemo } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, AlertTriangle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { useStockItems, useSubcategories } from '@/api/endpoints/stock';
import { fr } from '@/lib/i18n/fr';
import { StockItemsList } from './StockItemsPage';

export function StockSubCategoriesPage() {
  const { category: rawCategory } = useParams<{ category: string }>();
  const category = rawCategory ? decodeURIComponent(rawCategory) : '';
  const navigate = useNavigate();
  const { data: subs = [], isLoading: subsLoading } = useSubcategories(category);
  const { data: items = [], isLoading: itemsLoading } = useStockItems({ category });

  const subStats = useMemo(() => {
    const map = new Map<string, { count: number; alerts: number }>();
    items.forEach((it) => {
      const key = it.sous_categorie ?? '';
      if (!key) return;
      const cur = map.get(key) ?? { count: 0, alerts: 0 };
      cur.count += 1;
      if (it.quantite < it.seuil_alerte) cur.alerts += 1;
      map.set(key, cur);
    });
    return map;
  }, [items]);

  if (!category) return <Navigate to="/stock" replace />;
  if (subsLoading || itemsLoading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/stock')}>
          <ArrowLeft className="h-4 w-4" />
          {fr.stock.retourCategories}
        </Button>
      </div>

      <div>
        <h1 className="text-2xl font-bold">
          {fr.stock.sousCategoriesPour} {category}
        </h1>
      </div>

      {subs.length === 0 ? (
        <StockItemsList items={items} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subs.map((sc) => {
            const s = subStats.get(sc.nom_sous_categorie) ?? { count: 0, alerts: 0 };
            return (
              <Card
                key={sc.id}
                className="transition-all hover:shadow-md hover:-translate-y-0.5 cursor-pointer"
              >
                <Link
                  to={`/stock/${encodeURIComponent(category)}/${encodeURIComponent(sc.nom_sous_categorie)}`}
                  className="block"
                >
                  <CardContent className="p-5 space-y-3">
                    <div className="flex items-start justify-between">
                      <h2 className="text-lg font-semibold">{sc.nom_sous_categorie}</h2>
                      {s.alerts > 0 && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-terracotta-100 px-2 py-0.5 text-xs font-semibold text-terracotta-800">
                          <AlertTriangle className="h-3 w-3" />
                          {s.alerts}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {s.count} {fr.stock.nombreArticles.toLowerCase()}
                    </p>
                    <Button variant="outline" fullWidth>
                      {fr.stock.consulter} {sc.nom_sous_categorie}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </CardContent>
                </Link>
              </Card>
            );
          })}
        </div>
      )}

      {items.length === 0 && subs.length === 0 && <EmptyState title={fr.stock.aucunCat} />}
    </div>
  );
}
