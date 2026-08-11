import { fr } from '@/lib/i18n/fr';

interface AttachmentNamesPreviewProps {
  names: string[];
}

/**
 * Aperçu des noms de fichiers réellement transmis à la comptabilité.
 *
 * Le déposant corrige une faute de frappe avant l'envoi plutôt qu'après. Le
 * bloc était recopié à l'identique dans le dépôt de facture et dans la note de
 * frais ; seules les règles de repli du libellé diffèrent d'un écran à l'autre,
 * elles restent donc dans chaque page.
 */
export function AttachmentNamesPreview({ names }: AttachmentNamesPreviewProps) {
  if (names.length === 0) return null;

  return (
    <div className="rounded-md border bg-muted/40 p-3">
      <p className="text-xs font-medium">{fr.invoices.apercuNomFichier}</p>
      <ul className="mt-1 space-y-0.5">
        {names.map((name) => (
          <li key={name} className="font-mono text-xs text-muted-foreground">
            {name}
          </li>
        ))}
      </ul>
    </div>
  );
}
