import { describe, expect, it } from 'vitest';
import {
  formatCents,
  formatCurrency,
  formatDate,
  formatFileSize,
  formatNumber,
  parseDateSafe,
} from './format';

// `Intl.NumberFormat('fr-FR')` insère un NBSP (U+202F en Node ≥ 18) entre la
// valeur et le symbole. On normalise pour tester de manière robuste.
function normalizeSpaces(s: string): string {
  return s.replace(/[  ]/g, ' ');
}

describe('lib/format', () => {
  describe('formatCents', () => {
    it('formats 1500 cents as "15.00 €"', () => {
      expect(formatCents(1500)).toBe('15.00 €');
    });

    it('formats 0 cents as "0.00 €"', () => {
      expect(formatCents(0)).toBe('0.00 €');
    });

    it('returns "—" for null / undefined / NaN', () => {
      expect(formatCents(null)).toBe('—');
      expect(formatCents(undefined)).toBe('—');
      expect(formatCents(NaN)).toBe('—');
    });
  });

  describe('formatNumber', () => {
    it('formats 1234 with French locale separator', () => {
      expect(normalizeSpaces(formatNumber(1234))).toBe('1 234');
    });

    it('returns "—" for null / NaN', () => {
      expect(formatNumber(null)).toBe('—');
      expect(formatNumber(NaN)).toBe('—');
    });
  });

  describe('formatCurrency', () => {
    it('returns a euro-prefixed FR-formatted string', () => {
      const out = normalizeSpaces(formatCurrency(12.5));
      expect(out).toContain('12,50');
      expect(out).toContain('€');
    });

    it('returns "—" for nullish input', () => {
      expect(formatCurrency(undefined)).toBe('—');
    });
  });

  describe('parseDateSafe', () => {
    it('parses an ISO string', () => {
      const d = parseDateSafe('2025-01-15T10:00:00Z');
      expect(d).toBeInstanceOf(Date);
    });

    it('returns null for invalid input', () => {
      expect(parseDateSafe('not a date')).toBeNull();
      expect(parseDateSafe(null)).toBeNull();
    });
  });

  describe('formatDate', () => {
    it('formats an ISO string with default pattern', () => {
      // 2025-01-15 → "15/01/2025"
      expect(formatDate('2025-01-15T10:00:00Z')).toBe('15/01/2025');
    });

    it('returns "—" for invalid input', () => {
      expect(formatDate('garbage')).toBe('—');
    });
  });

  describe('formatFileSize', () => {
    it('returns "0 B" for 0 bytes', () => {
      expect(formatFileSize(0)).toBe('0 B');
    });

    it('formats 1024 as "1.0 KB"', () => {
      expect(formatFileSize(1024)).toBe('1.0 KB');
    });

    it('formats megabytes', () => {
      expect(formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB');
    });
  });
});
