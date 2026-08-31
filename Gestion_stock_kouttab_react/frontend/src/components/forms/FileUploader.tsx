import { useCallback, useId, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { Upload, X, FileText, Crop } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatFileSize } from '@/lib/format';
import { DocumentScanner } from '@/components/scanner/DocumentScanner';
import { fr } from '@/lib/i18n/fr';

interface FileUploaderProps {
  accept?: string;
  multiple?: boolean;
  maxSizeMb?: number;
  files: File[];
  onChange: (files: File[]) => void;
  label?: string;
  helperText?: string;
  disabled?: boolean;
  /**
   * Propose le recadrage des images déposées, avec les poignées du scanner.
   *
   * Une photo de ticket glissée depuis l'ordinateur ou la photothèque partait
   * **entière** : le ticket occupe un dixième de l'image, le reste est la
   * table. Le comptable recevait un PDF lourd où il fallait chercher la pièce,
   * alors que le même besoin était déjà résolu côté scanner.
   *
   * Hors des dépôts de justificatifs — import CSV, RIB — l'option reste fermée :
   * recadrer un fichier de données n'a aucun sens.
   */
  recadrage?: boolean;
}

export function FileUploader({
  accept = '*',
  multiple = true,
  maxSizeMb = 10,
  files,
  onChange,
  label = 'Glissez vos fichiers ici ou cliquez pour sélectionner',
  helperText,
  disabled,
  recadrage = false,
}: FileUploaderProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fichier en cours de recadrage.
   *
   * Un seul à la fois, et le dialogue s'ouvre sur celui-ci : enchaîner
   * automatiquement les cinq pièces d'un dépôt enfermerait le déposant dans une
   * suite de fenêtres sans savoir combien il en reste. Le recadrage se demande
   * donc pièce par pièce, depuis la liste.
   */
  const [aRecadrer, setARecadrer] = useState<{ file: File; index: number } | null>(null);

  /** Une image que ce navigateur sait afficher — donc recadrer. */
  const estRecadrable = useCallback(
    (f: File) => recadrage && f.type.startsWith('image/'),
    [recadrage],
  );

  const handleAdd = (newFiles: FileList | File[]) => {
    setError(null);
    const arr = Array.from(newFiles);
    const oversized = arr.find((f) => f.size > maxSizeMb * 1024 * 1024);
    if (oversized) {
      setError(`Le fichier "${oversized.name}" dépasse ${maxSizeMb} Mo.`);
      return;
    }
    const suivants = multiple ? [...files, ...arr] : arr.slice(0, 1);
    onChange(suivants);

    // Ouverture directe sur la première image ajoutée : c'est le geste attendu
    // après un dépôt, et le proposer sans l'imposer ferait manquer l'essentiel
    // du gain — personne ne pense à recadrer une image déjà déposée.
    const premiere = arr.find(estRecadrable);
    if (premiere) {
      setARecadrer({ file: premiere, index: suivants.indexOf(premiere) });
    }
  };

  /** Remplace la pièce d'origine par sa version recadrée, à sa place. */
  const remplacer = (recadre: File) => {
    if (!aRecadrer) return;
    onChange(files.map((f, i) => (i === aRecadrer.index ? recadre : f)));
    setARecadrer(null);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    handleAdd(e.target.files);
    e.target.value = '';
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (disabled) return;
    if (e.dataTransfer.files?.length) handleAdd(e.dataTransfer.files);
  };

  const handleDrag = (e: DragEvent<HTMLDivElement>, active: boolean) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setDragActive(active);
  };

  const remove = (idx: number) => {
    onChange(files.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-3">
      <div
        onDragEnter={(e) => handleDrag(e, true)}
        onDragOver={(e) => handleDrag(e, true)}
        onDragLeave={(e) => handleDrag(e, false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border px-4 py-8 text-center cursor-pointer transition-colors hover:bg-muted/30',
          dragActive && 'border-primary bg-primary/5',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <Upload className="h-6 w-6 text-muted-foreground" />
        <p className="text-sm font-medium">{label}</p>
        {helperText && <p className="text-xs text-muted-foreground">{helperText}</p>}
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={disabled}
          onChange={handleChange}
          className="sr-only"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              className="flex items-center justify-between gap-3 rounded-md border bg-muted/20 px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                <span className="truncate">{f.name}</span>
                <span className="text-xs text-muted-foreground flex-shrink-0">
                  {formatFileSize(f.size)}
                </span>
              </div>
              <div className="flex flex-shrink-0 items-center">
                {/* Reproposé sur chaque image : le cadrage se rejuge une fois la
                    pièce vue dans la liste, et une image ajoutée après coup
                    n'aurait sinon aucun moyen d'être recadrée. */}
                {estRecadrable(f) && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      setARecadrer({ file: f, index: i });
                    }}
                    aria-label={`${fr.scanner.recadrer} ${f.name}`}
                    disabled={disabled}
                  >
                    <Crop className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(i);
                  }}
                  aria-label={`Retirer ${f.name}`}
                  disabled={disabled}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Monté seulement quand un recadrage est demandé : le scanner ouvre la
          caméra à l'affichage, et le laisser monté allumerait l'objectif à
          chaque dépôt de fichier. La clé force un remontage propre d'une pièce
          à l'autre, sinon la seconde s'ouvrirait sur le cadre de la première. */}
      {aRecadrer && (
        <DocumentScanner
          key={`${aRecadrer.index}-${aRecadrer.file.name}`}
          open
          fichierInitial={aRecadrer.file}
          onClose={() => setARecadrer(null)}
          onScanned={remplacer}
        />
      )}
    </div>
  );
}
