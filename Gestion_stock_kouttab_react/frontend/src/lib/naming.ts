/**
 * Nomenclature des fichiers envoyés au service comptable.
 *
 * Format : `{Pôle}_{Événement}_{AAAA-MM-JJ}.pdf`
 *
 * ⚠️ Ce module duplique volontairement `backend/app/services/naming.py`.
 * Le backend reste seul juge du nom réellement produit ; cette copie sert
 * uniquement à montrer au déposant, avant validation, le nom que portera sa
 * pièce. Les deux implémentations sont couvertes par la **même table de cas**
 * (`naming.test.ts` / `test_naming.py`) : toute divergence casse un test.
 */

export const MAX_COMPONENT_LEN = 40;
export const MAX_STEM_LEN = 120;
export const MISSING = 'NC';

/** Caractères que la normalisation NFKD ne décompose pas. */
const EXPLICIT_REPLACEMENTS: Array<[string, string]> = [
  ['œ', 'oe'],
  ['Œ', 'OE'],
  ['æ', 'ae'],
  ['Æ', 'AE'],
  ['ß', 'ss'],
  ['€', 'EUR'],
  ['$', 'USD'],
  ['£', 'GBP'],
  ['&', 'et'],
  ['@', 'at'],
  ['°', 'deg'],
  ['’', ''],
  ["'", ''],
  ['`', ''],
  ['"', ''],
  ['«', ''],
  ['»', ''],
];

/** Un fichier nommé `CON.pdf` est indécompressable sous Windows. */
const WINDOWS_RESERVED = new Set([
  'CON',
  'PRN',
  'AUX',
  'NUL',
  ...Array.from({ length: 9 }, (_, i) => `COM${i + 1}`),
  ...Array.from({ length: 9 }, (_, i) => `LPT${i + 1}`),
]);

export function slugifyComponent(
  value: string | null | undefined,
  maxLen = MAX_COMPONENT_LEN,
): string {
  if (value === null || value === undefined) return MISSING;

  let text = String(value);
  for (const [from, to] of EXPLICIT_REPLACEMENTS) {
    text = text.split(from).join(to);
  }

  // Décomposition puis suppression des diacritiques : é -> e, ç -> c.
  text = text.normalize('NFKD').replace(/[̀-ͯ]/g, '');
  // Filet de sécurité : alphabets non translittérables (cyrillique, CJK…).
  // Équivalent de `encode('ascii', 'ignore')` côté Python. Écrit sans regex :
  // une classe de caractères couvrant \x00 déclenche la règle no-control-regex.
  text = Array.from(text)
    .filter((ch) => ch.charCodeAt(0) < 128)
    .join('');

  // Neutralise d'un coup les interdits Windows, les caractères de contrôle,
  // les espaces et les points.
  text = text.replace(/[^A-Za-z0-9]+/g, '-');
  text = text.replace(/-{2,}/g, '-').replace(/^-+|-+$/g, '');

  if (!text) return MISSING;

  if (text.length > maxLen) {
    text = text.slice(0, maxLen);
    const lastDash = text.slice(1).lastIndexOf('-');
    if (lastDash !== -1) text = text.slice(0, lastDash + 1);
    text = text.replace(/^-+|-+$/g, '');
  }

  if (!text) return MISSING;
  if (WINDOWS_RESERVED.has(text.toUpperCase())) return `_${text}`;
  return text;
}

/** Date au format AAAA-MM-JJ. Accepte une chaîne de `<input type="date">`. */
export function formatDateComponent(value: string | Date | null | undefined): string {
  if (!value) return MISSING;
  if (typeof value === 'string') {
    const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? match[0] : MISSING;
  }
  if (Number.isNaN(value.getTime())) return MISSING;
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, '0');
  const day = `${value.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function buildAttachmentStem(
  components: Array<string | null | undefined>,
  dateValue: string | Date | null | undefined,
): string {
  const parts = components.map((c) => slugifyComponent(c));
  parts.push(formatDateComponent(dateValue));
  let stem = parts.join('_');
  if (stem.length > MAX_STEM_LEN) {
    stem = stem.slice(0, MAX_STEM_LEN).replace(/^[-_]+|[-_]+$/g, '');
  }
  return stem;
}

export function buildAttachmentFilename(
  components: Array<string | null | undefined>,
  dateValue: string | Date | null | undefined,
  extension = 'pdf',
): string {
  const ext = extension.replace(/^\./, '').toLowerCase() || 'pdf';
  return `${buildAttachmentStem(components, dateValue)}.${ext}`;
}

/**
 * Rend uniques des noms identiques en suffixant `-2`, `-3`…
 *
 * Les justificatifs d'un même dépôt partagent pôle, événement et date : sans
 * cette passe, les pièces jointes porteraient toutes le même nom.
 */
export function deduplicateFilenames(names: string[]): string[] {
  const seen = new Map<string, number>();
  return names.map((name) => {
    const dot = name.lastIndexOf('.');
    let stem = dot > 0 ? name.slice(0, dot) : name;
    const ext = dot > 0 ? name.slice(dot + 1) : '';

    const key = name.toLowerCase();
    const count = (seen.get(key) ?? 0) + 1;
    seen.set(key, count);
    if (count === 1) return name;

    const suffix = `-${count}`;
    // Laisse la place au suffixe : sinon la troncature le supprimerait et la
    // collision réapparaîtrait silencieusement.
    if (stem.length + suffix.length > MAX_STEM_LEN) {
      stem = stem.slice(0, MAX_STEM_LEN - suffix.length).replace(/^[-_]+|[-_]+$/g, '');
    }
    return ext ? `${stem}${suffix}.${ext}` : `${stem}${suffix}`;
  });
}
