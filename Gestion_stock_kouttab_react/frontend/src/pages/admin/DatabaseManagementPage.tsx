import { useState } from 'react';
import { BarChart3, Database, Download, Upload } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { FileUploader } from '@/components/forms/FileUploader';
import { useDatabaseStatus, useExportDatabase, useImportDatabase } from '@/api/endpoints/admin';
import { useToast } from '@/hooks/useToast';
import { formatNumber } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

export function DatabaseManagementPage() {
  const { data: status, isLoading } = useDatabaseStatus();
  const exportMut = useExportDatabase();
  const importMut = useImportDatabase();
  const toast = useToast();

  const [files, setFiles] = useState<File[]>([]);
  const [confirmed, setConfirmed] = useState(false);

  const handleExport = () => {
    exportMut.mutate(undefined, { onSuccess: () => toast.success('Export téléchargé') });
  };

  const handleImport = () => {
    if (!confirmed) {
      toast.warning('Veuillez cocher la confirmation.');
      return;
    }
    if (files.length === 0) {
      toast.warning('Sélectionnez au moins un fichier CSV.');
      return;
    }
    importMut.mutate(files, {
      onSuccess: (res) =>
        toast.success('Import terminé', `${res.tables.length} table(s) traitée(s)`),
    });
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 font-serif text-2xl font-bold text-forest">
          <Database className="h-6 w-6" aria-hidden />
          {fr.admin.databaseTitle}
        </h1>
        <p className="text-sm text-muted-foreground">
          Réservé au Super Admin. Manipuler avec précaution.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4" aria-hidden />
            {fr.admin.diagnosticTitle}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-40" />
          ) : !status ? (
            <Alert variant="destructive">
              <AlertDescription>Impossible de récupérer l&apos;état de la BDD.</AlertDescription>
            </Alert>
          ) : (
            <>
              <Alert variant={status.ok ? 'success' : 'destructive'} className="mb-3">
                <AlertDescription>
                  Connexion : <strong>{status.ok ? 'OK' : 'KO'}</strong> · Total lignes :{' '}
                  <strong>{formatNumber(status.total_rows)}</strong>
                </AlertDescription>
              </Alert>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Table</TableHead>
                    <TableHead className="text-right">Lignes</TableHead>
                    <TableHead className="text-right">Taille</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {status.tables.map((t) => (
                    <TableRow key={t.name}>
                      <TableCell className="font-mono">{t.name}</TableCell>
                      <TableCell className="text-right">{formatNumber(t.rows)}</TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {t.size_kb ? `${t.size_kb.toFixed(1)} KB` : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">⬇️ {fr.admin.exportTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">
            Génère un ZIP horodaté contenant les CSVs de toutes les tables (sauf <code>Admins</code>{' '}
            pour des raisons de sécurité).
          </p>
          <Button onClick={handleExport} loading={exportMut.isPending}>
            <Download className="h-4 w-4" />
            Exporter
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">⬆️ {fr.admin.importTitle}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Alert variant="warning">
            <AlertDescription>
              Attention : l&apos;import remplace les données existantes par le contenu des CSVs.
            </AlertDescription>
          </Alert>
          <FileUploader
            accept=".csv,text/csv"
            files={files}
            onChange={setFiles}
            multiple
            helperText="Un fichier CSV par table à importer."
          />
          <div className="flex items-center gap-2">
            <Checkbox
              id="confirm-import"
              checked={confirmed}
              onCheckedChange={(c) => setConfirmed(Boolean(c))}
            />
            <Label htmlFor="confirm-import">{fr.admin.confirmImport}</Label>
          </div>
          <Button onClick={handleImport} loading={importMut.isPending} disabled={!confirmed}>
            <Upload className="h-4 w-4" />
            Importer
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
