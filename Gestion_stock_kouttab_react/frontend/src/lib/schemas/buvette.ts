import { z } from 'zod';
import type { CaisseCategory } from '@/types/api';

/**
 * Onglet de la tablette de caisse, tel que le formulaire le manipule.
 *
 * `aucun` tient lieu de `null` : une liste déroulante Radix refuse une valeur
 * vide. La conversion se fait à l'envoi, par `ongletVersCategorie`.
 */
export const ONGLETS_CAISSE = ['aucun', 'sucre_sale', 'boissons', 'cafe'] as const;
export type OngletCaisse = (typeof ONGLETS_CAISSE)[number];

export function ongletVersCategorie(onglet: OngletCaisse): CaisseCategory | null {
  return onglet === 'aucun' ? null : onglet;
}

export function categorieVersOnglet(categorie: CaisseCategory | null | undefined): OngletCaisse {
  return categorie ?? 'aucun';
}

/**
 * Schéma de création d'un produit buvette.
 * Le prix est saisi en euros (format décimal) puis converti en cents avant envoi.
 */
export const createBuvetteProductSchema = z.object({
  name: z.string().min(1, 'Nom obligatoire').max(200),
  price_euros: z.coerce.number({ invalid_type_error: 'Prix invalide' }).min(0, 'Doit être ≥ 0'),
  quantity: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  seuil_alerte: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  emoji: z.string().min(1, 'Emoji obligatoire').max(8),
  onglet_caisse: z.enum(ONGLETS_CAISSE),
  helloasso_tier_id: z
    .preprocess(
      (v) => (v === '' || v === null || v === undefined ? null : Number(v)),
      z.number().int().positive().nullable(),
    )
    .nullable()
    .optional(),
});

export type CreateBuvetteProductFormValues = z.infer<typeof createBuvetteProductSchema>;

/**
 * Schéma d'ajustement d'un produit buvette.
 */
export const adjustBuvetteProductSchema = z.object({
  quantity: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  seuil_alerte: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  emoji: z.string().min(1, 'Emoji obligatoire').max(8),
  onglet_caisse: z.enum(ONGLETS_CAISSE),
});

export type AdjustBuvetteProductFormValues = z.infer<typeof adjustBuvetteProductSchema>;

/**
 * Schéma de création d'un produit buvette à partir d'un code-barres scanné.
 * `barcode` est requis ; `helloasso_tier_id` reste null.
 */
export const buvetteProductFromBarcodeSchema = z.object({
  barcode: z.string().min(1, 'Code-barres obligatoire'),
  name: z.string().min(1, 'Nom obligatoire').max(200),
  price_euros: z.coerce.number({ invalid_type_error: 'Prix invalide' }).min(0, 'Doit être ≥ 0'),
  quantity: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  seuil_alerte: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  emoji: z.string().min(1, 'Emoji obligatoire').max(8),
});

export type BuvetteProductFromBarcodeFormValues = z.infer<typeof buvetteProductFromBarcodeSchema>;

/**
 * Schéma de configuration d'un webhook.
 * URL optionnelle (le backend utilise une URL par défaut).
 */
export const webhookConfigureSchema = z.object({
  url: z
    .string()
    .url('URL invalide')
    .optional()
    .or(z.literal('').transform(() => undefined)),
});

export type WebhookConfigureFormValues = z.infer<typeof webhookConfigureSchema>;
