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

// Bornes alignées sur `LoginIn` (backend/app/schemas/auth.py), qui accepte
// désormais un identifiant **ou** une adresse e-mail : les bénévoles retiennent
// leur adresse, rarement l'identifiant choisi à l'inscription.
//
// La borne haute était de 20 caractères, celle d'un identifiant : toute adresse
// repartait en 422 « Données invalides » sans que rien n'indique pourquoi.
// Le regex de `usernameSchema` n'est pas repris ici : il contraint la création
// d'un compte, pas la connexion d'un compte existant.
export const loginSchema = z.object({
  username: z.string().min(3, 'Au moins 3 caractères').max(254, 'Saisie trop longue'),
  password: z.string().min(1, 'Champ obligatoire'),
});

/** Demande de réinitialisation : identifiant ou adresse, comme à la connexion. */
export const forgotPasswordSchema = z.object({
  identifiant: z.string().min(3, 'Au moins 3 caractères').max(254, 'Saisie trop longue'),
});

export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    password: passwordSchema,
    confirmPassword: z.string().min(1, 'Champ obligatoire'),
  })
  .refine((v) => v.password === v.confirmPassword, {
    message: 'Les mots de passe ne correspondent pas',
    path: ['confirmPassword'],
  });

export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

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
