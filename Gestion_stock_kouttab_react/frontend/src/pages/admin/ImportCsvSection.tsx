import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useImportCsv } from '@/api/endpoints/stock';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';

export function ImportCsvSection() {
  const importMut = useImportCsv();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [skiprows, setSkiprows] = useState(6);
  const [report, setReport] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null);

  const handleSubmit = async () => {
    if (!file) {
      toast.warning('Sélectionnez un fichier CSV.');
      return;
    }
    try {
      const res = await importMut.mutateAsync({ file, skiprows });
      setReport(res);
      toast.success(
        'Import terminé',
        `${res.imported} importés, ${res.skipped} ignorés, ${res.errors.length} erreurs`,
      );
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">📁 Importation CSV</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert variant="info">
          <AlertDescription>
            Colonnes attendues : <code>Catégorie, Sous-catégorie, Nom de l&apos;article, Quantité initiale</code>
          </AlertDescription>
        </Alert>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Fichier CSV</Label>
            <Input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Skiprows (lignes d&apos;en-tête à ignorer)</Label>
            <Input
              type="number"
              min={0}
              value={skiprows}
              onChange={(e) => setSkiprows(Number(e.target.value) || 0)}
            />
          </div>
        </div>

        <Button onClick={handleSubmit} loading={importMut.isPending}>
          Importer
        </Button>

        {report && (
          <div className="rounded-md border bg-muted/20 p-3 text-sm space-y-1">
            <p>
              ✅ Importés : <strong>{report.imported}</strong>
            </p>
            <p>
              ➖ Ignorés : <strong>{report.skipped}</strong>
            </p>
            <p>
              ⚠️ Erreurs : <strong>{report.errors.length}</strong>
            </p>
            {report.errors.length > 0 && (
              <ul className="mt-2 list-disc list-inside text-xs text-muted-foreground space-y-0.5">
                {report.errors.slice(0, 10).map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
