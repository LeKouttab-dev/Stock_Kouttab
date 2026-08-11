import { z } from 'zod';

export const stockItemSchema = z.object({
  nom: z.string().min(1, "Nom de l'article obligatoire"),
  categorie: z.string().min(1, 'Catégorie obligatoire'),
  sous_categorie: z.string().nullable().optional(),
  quantite: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  seuil_alerte: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  emoji: z.string().min(1, 'Emoji obligatoire'),
});

export type StockItemFormValues = z.infer<typeof stockItemSchema>;

export const stockItemFromBarcodeSchema = z.object({
  barcode: z.string().min(1, 'Code-barres obligatoire'),
  nom: z.string().min(1, "Nom de l'article obligatoire"),
  categorie: z.string().min(1, 'Catégorie obligatoire'),
  sous_categorie: z
    .string()
    .nullable()
    .optional()
    .transform((v) => (v === '' ? null : (v ?? null))),
  quantite: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  seuil_alerte: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
  emoji: z.string().min(1, 'Emoji obligatoire'),
});

export type StockItemFromBarcodeFormValues = z.infer<typeof stockItemFromBarcodeSchema>;

export const requestModificationSchema = z.object({
  quantite_demandee: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
});

export type RequestModificationFormValues = z.infer<typeof requestModificationSchema>;

export const directModificationSchema = z.object({
  quantite: z.coerce.number().int().min(0, 'Doit être ≥ 0'),
});

export type DirectModificationFormValues = z.infer<typeof directModificationSchema>;

export const categorySchema = z.object({
  nom: z.string().min(1, 'Nom obligatoire').max(100),
});

export type CategoryFormValues = z.infer<typeof categorySchema>;

export const subCategorySchema = z.object({
  nom_categorie: z.string().min(1),
  nom_sous_categorie: z.string().min(1, 'Nom obligatoire').max(100),
});

export type SubCategoryFormValues = z.infer<typeof subCategorySchema>;
