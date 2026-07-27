import { format, parseISO, isValid } from 'date-fns';
import { fr } from 'date-fns/locale';

export function formatCurrency(value: number | null | undefined, currency = 'EUR'): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('fr-FR').format(value);
}

export function parseDateSafe(input: string | Date | null | undefined): Date | null {
  if (!input) return null;
  if (input instanceof Date) return isValid(input) ? input : null;
  try {
    const d = parseISO(input);
    if (isValid(d)) return d;
    const fallback = new Date(input);
    return isValid(fallback) ? fallback : null;
  } catch {
    return null;
  }
}

export function formatDate(input: string | Date | null | undefined, pattern = 'dd/MM/yyyy'): string {
  const d = parseDateSafe(input);
  return d ? format(d, pattern, { locale: fr }) : '—';
}

export function formatDateTime(input: string | Date | null | undefined): string {
  return formatDate(input, 'dd/MM/yyyy HH:mm');
}

export function formatCents(cents: number | null | undefined): string {
  if (cents === null || cents === undefined || Number.isNaN(cents)) return '—';
  return `${(cents / 100).toFixed(2)} €`;
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}
