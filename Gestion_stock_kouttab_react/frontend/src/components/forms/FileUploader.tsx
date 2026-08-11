import { useId, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { Upload, X, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatFileSize } from '@/lib/format';

interface FileUploaderProps {
  accept?: string;
  multiple?: boolean;
  maxSizeMb?: number;
  files: File[];
  onChange: (files: File[]) => void;
  label?: string;
  helperText?: string;
  disabled?: boolean;
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
}: FileUploaderProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = (newFiles: FileList | File[]) => {
    setError(null);
    const arr = Array.from(newFiles);
    const oversized = arr.find((f) => f.size > maxSizeMb * 1024 * 1024);
    if (oversized) {
      setError(`Le fichier "${oversized.name}" dépasse ${maxSizeMb} Mo.`);
      return;
    }
    onChange(multiple ? [...files, ...arr] : arr.slice(0, 1));
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
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
