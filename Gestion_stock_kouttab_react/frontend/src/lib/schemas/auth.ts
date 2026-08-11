import { z } from 'zod';

export const passwordSchema = z
  .string()
  .min(8, 'Le mot de passe doit contenir au moins 8 caractères')
  .regex(/[A-Z]/, 'Le mot de passe doit contenir au moins une majuscule')
  .regex(/[a-z]/, 'Le mot de passe doit contenir au moins une minuscule')
  .regex(/[0-9]/, 'Le mot de passe doit contenir au moins un chiffre')
  .regex(
    /[!@#$%^&*(),.?":{}|<>_\-+=/\\[\]]/,
    'Le mot de passe doit contenir au moins un caractère spécial',
  );

export const usernameSchema = z
  .string()
  .min(3, "Le nom d'utilisateur doit contenir au moins 3 caractères")
  .max(20, "Le nom d'utilisateur ne peut pas dépasser 20 caractères")
  .regex(/^[a-zA-Z0-9_-]+$/, 'Caractères autorisés : lettres, chiffres, tirets et underscores');

// Les bornes reprennent celles de `LoginIn` cote backend (schemas/auth.py).
// Sans elles, une saisie hors bornes — typiquement une adresse email, plus
// longue que 20 caracteres — partait a l'API et revenait en 422 « Donnees
// invalides », incomprehensible pour qui essaie juste de se connecter.
// Le regex de `usernameSchema` n'est volontairement pas repris : il contraint
// la creation d'un compte, pas la connexion d'un compte existant.
export const loginSchema = z.object({
  username: z
    .string()
    .min(3, "Le nom d'utilisateur doit contenir au moins 3 caractères")
    .max(20, "Le nom d'utilisateur ne peut pas dépasser 20 caractères"),
  password: z.string().min(1, 'Champ obligatoire'),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const signupSchema = z
  .object({
    username: usernameSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, 'Champ obligatoire'),
    // Pas de `role` : il est imposé côté serveur ('Benevole') et un Super Admin
    // le fait évoluer ensuite. Cf. SignupPage.
    nom: z.string().min(1, 'Nom obligatoire'),
    prenom: z.string().min(1, 'Prénom obligatoire'),
    email: z.string().email('Email invalide'),
    telephone: z.string().optional().or(z.literal('')),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirmPassword'],
  });

export type SignupFormValues = z.infer<typeof signupSchema>;

export const adminSetupSchema = z
  .object({
    username: usernameSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, 'Champ obligatoire'),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirmPassword'],
  });

export type AdminSetupFormValues = z.infer<typeof adminSetupSchema>;

export const profileSchema = z.object({
  nom: z.string().min(1, 'Nom obligatoire'),
  prenom: z.string().min(1, 'Prénom obligatoire'),
  email: z.string().email('Email invalide'),
  telephone: z.string().optional().or(z.literal('')),
  rib: z.string().optional().or(z.literal('')),
});

export type ProfileFormValues = z.infer<typeof profileSchema>;

/** Calcule un score 0..4 pour la force du mot de passe. */
export function passwordStrength(pw: string): {
  score: number;
  checks: { label: string; ok: boolean }[];
} {
  const checks = [
    { label: '8 caractères ou plus', ok: pw.length >= 8 },
    { label: 'Au moins une majuscule', ok: /[A-Z]/.test(pw) },
    { label: 'Au moins un chiffre', ok: /[0-9]/.test(pw) },
    { label: 'Au moins un caractère spécial', ok: /[!@#$%^&*(),.?":{}|<>_\-+=/\\[\]]/.test(pw) },
  ];
  const score = checks.filter((c) => c.ok).length;
  return { score, checks };
}
