import { useState } from 'react';
import { ChevronDown, ChevronRight, Download, FileSpreadsheet } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useReimbursements, reimbursementDocumentPath } from '@/api/endpoints/reimbursements';
import { useDownloadAttachment } from '@/hooks/useDownloadAttachment';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';
import type { Reimbursement } from '@/types/api';

/**
 * Les remboursements reçus, et leur justificatif.
 *
 * L'écran manquait entièrement : le PDF et le tableur étaient produits à chaque
 * versement, joints au courriel de la comptabilité, et **montrés à personne**.
 * Le bénévole voyait une pastille verte « Remboursée » sur sa note et rien
 * d'autre — ni date de versement, ni montant, ni moyen, ni preuve à produire.
 *
 * L'API l'autorisait déjà à télécharger le sien ; il manquait le bouton.
 */
export function ReimbursementsList() {
  const { data: remboursements = [], isLoading } = useReimbursements();
  const [ouvert, setOuvert] = useState<number | null>(null);

  if (isLoading) return <LoadingSpinner fullPage />;
  if (remboursements.length === 0) {
    return <EmptyState title={fr.reimbursements.aucunHistorique} />;
  }

  return (
    <div className="space-y-3">
      {remboursements.map((remboursement) => (
        <FicheRemboursement
          key={remboursement.id}
          remboursement={remboursement}
          ouverte={ouvert === remboursement.id}
          onToggle={() => setOuvert(ouvert === remboursement.id ? null : remboursement.id)}
        />
      ))}
    </div>
  );
}

function FicheRemboursement({
  remboursement,
  ouverte,
  onToggle,
}: {
  remboursement: Reimbursement;
  ouverte: boolean;
  onToggle: () => void;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <button
          onClick={onToggle}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30"
        >
          <div className="flex min-w-0 items-center gap-2">
            {ouverte ? (
              <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            )}
            <span className="truncate font-medium">
              {formatDate(remboursement.date_remboursement)} —{' '}
              {formatCurrency(Number(remboursement.montant_total))} {fr.reimbursements.verse}
            </span>
          </div>
          <span className="flex-shrink-0 text-xs text-muted-foreground">
            {remboursement.expenses.length} {fr.reimbursements.notesSoldees}
          </span>
        </button>

        {ouverte && <DetailRemboursement remboursement={remboursement} />}
      </CardContent>
    </Card>
  );
}

function DetailRemboursement({ remboursement }: { remboursement: Reimbursement }) {
  const { download, downloadingId } = useDownloadAttachment();

  return (
    <div className="space-y-3 border-t bg-muted/10 px-4 py-4 text-sm">
      <div className="grid gap-1 md:grid-cols-2">
        {/* Visible seulement pour la comptabilité : un bénévole ne voit que
            ses propres versements, répéter son nom n'apprend rien. */}
        {remboursement.user_full_name && (
          <p>
            <strong>{fr.expenses.benevole} :</strong> {remboursement.user_full_name}
          </p>
        )}
        <p>
          <strong>{fr.reimbursements.emisLe} :</strong>{' '}
          {formatDate(remboursement.date_remboursement)}
        </p>
        <p>
          <strong>{fr.reimbursements.moyen} :</strong> {remboursement.moyen}
        </p>
        <p>
          <strong>{fr.reimbursements.etablissement} :</strong> {remboursement.etablissement}
        </p>
        <p>
          <strong>{fr.reimbursements.approuvePar} :</strong> {remboursement.approuve_par}
        </p>
      </div>

      {remboursement.commentaire && (
        <p>
          <strong>{fr.reimbursements.commentaire} :</strong> {remboursement.commentaire}
        </p>
      )}

      <div>
        <p className="font-medium">{fr.expenses.notesSoldeesTitre} :</p>
        <ul className="mt-1 space-y-0.5">
          {remboursement.expenses.map((note) => (
            <li key={note.id} className="text-muted-foreground">
              {formatDate(note.date_depense)} — {formatCurrency(Number(note.montant))}
              {note.fournisseur ? ` — ${note.fournisseur}` : ''}
            </li>
          ))}
        </ul>
      </div>

      {/* `a_pdf` regarde la présence réelle du document, et non celle d'un
          chemin : promettre un téléchargement qui rend un 404 est pire que ne
          rien proposer. */}
      <div className="flex flex-wrap gap-2">
        {remboursement.a_pdf && (
          <Button
            variant="outline"
            size="sm"
            disabled={downloadingId === remboursement.id}
            onClick={() =>
              download(
                reimbursementDocumentPath(remboursement.id, 'pdf'),
                `NDF-${remboursement.id}.pdf`,
                remboursement.id,
              )
            }
          >
            <Download className="mr-1 h-4 w-4" />
            {fr.reimbursements.justificatifPdf}
          </Button>
        )}
        {remboursement.a_xlsx && (
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              download(
                reimbursementDocumentPath(remboursement.id, 'xlsx'),
                `NDF-${remboursement.id}.xlsx`,
              )
            }
          >
            <FileSpreadsheet className="mr-1 h-4 w-4" />
            {fr.reimbursements.justificatifXlsx}
          </Button>
        )}
      </div>
    </div>
  );
}
