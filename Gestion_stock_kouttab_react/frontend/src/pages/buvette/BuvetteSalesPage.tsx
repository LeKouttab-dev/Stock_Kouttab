import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useBuvetteSales } from '@/api/endpoints/buvette';
import { fr } from '@/lib/i18n/fr';
import { formatCents, formatDateTime } from '@/lib/format';

const PAGE_SIZE = 50;

export function BuvetteSalesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const offset = page * PAGE_SIZE;

  const { data: sales = [], isLoading } = useBuvetteSales(PAGE_SIZE, offset);

  const hasNext = sales.length === PAGE_SIZE;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/buvette')}>
          <ArrowLeft className="h-4 w-4" />
          {fr.buvette.backToBuvette}
        </Button>
      </div>

      <h1 className="font-serif text-2xl font-bold text-forest">{fr.buvette.salesTitle}</h1>

      {isLoading ? (
        <Skeleton className="h-72" />
      ) : sales.length === 0 ? (
        <EmptyState title={fr.buvette.salesEmpty} />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{fr.buvette.soldAt}</TableHead>
                  <TableHead>{fr.buvette.product}</TableHead>
                  <TableHead className="text-right">{fr.buvette.qtySold}</TableHead>
                  <TableHead className="text-right">{fr.buvette.amount}</TableHead>
                  <TableHead>{fr.buvette.customer}</TableHead>
                  <TableHead>{fr.buvette.orderId}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sales.map((sale) => {
                  const customer = [sale.customer_first_name, sale.customer_last_name]
                    .filter(Boolean)
                    .join(' ');
                  return (
                    <TableRow key={sale.id}>
                      <TableCell className="whitespace-nowrap text-xs">
                        {formatDateTime(sale.sold_at ?? sale.processed_at)}
                      </TableCell>
                      <TableCell className="font-medium">
                        {sale.product_name_snapshot}
                      </TableCell>
                      <TableCell className="text-right">{sale.quantity_sold}</TableCell>
                      <TableCell className="text-right font-semibold">
                        {formatCents(sale.amount_cents)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {customer || '—'}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {sale.helloasso_order_id ?? '—'}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 0 || isLoading}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
        >
          {fr.common.previous}
        </Button>
        <span className="text-xs text-muted-foreground">
          {fr.buvette.page} {page + 1}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={!hasNext || isLoading}
          onClick={() => setPage((p) => p + 1)}
        >
          {fr.common.next}
        </Button>
      </div>
    </div>
  );
}
