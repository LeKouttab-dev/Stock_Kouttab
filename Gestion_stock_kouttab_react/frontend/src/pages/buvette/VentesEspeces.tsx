import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDateHeureParis } from '@/lib/buvette';
import { formatCents } from '@/lib/format';
import type { InventaireVenteEspeces } from '@/types/api';

interface Libelles {
  date: string;
  articles: string;
  montant: string;
  aucuneVente: string;
}

/** Ventes en espèces d'une période (clôture ou inventaire), heure de Paris. */
export function VentesEspeces({
  ventes,
  libelles,
}: {
  ventes: InventaireVenteEspeces[];
  libelles: Libelles;
}) {
  if (ventes.length === 0) {
    return <p className="text-sm text-muted-foreground">{libelles.aucuneVente}</p>;
  }
  return (
    <div className="max-h-80 overflow-auto rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{libelles.date}</TableHead>
            <TableHead>{libelles.articles}</TableHead>
            <TableHead className="text-right">{libelles.montant}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ventes.map((v) => (
            <TableRow key={v.cle}>
              <TableCell className="whitespace-nowrap text-xs">
                {formatDateHeureParis(v.sold_at)}
              </TableCell>
              <TableCell className="text-sm">
                {v.articles.map((a) => `${a.quantite} × ${a.nom}`).join(', ')}
              </TableCell>
              <TableCell className="text-right font-semibold">
                {formatCents(v.total_cents)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
