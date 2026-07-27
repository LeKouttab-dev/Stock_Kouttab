import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { PasswordStrengthMeter } from '@/components/forms/PasswordStrengthMeter';
import { useSignup } from '@/api/endpoints/auth';
import { signupSchema, type SignupFormValues } from '@/lib/schemas/auth';
import { fr } from '@/lib/i18n/fr';
import { useToast } from '@/hooks/useToast';

export function SignupPage() {
  const navigate = useNavigate();
  const signupMutation = useSignup();
  const { success } = useToast();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      username: '',
      password: '',
      confirmPassword: '',
      nom: '',
      prenom: '',
      email: '',
      telephone: '',
    },
  });

  const password = watch('password');

  const onSubmit = async (values: SignupFormValues) => {
    try {
      await signupMutation.mutateAsync({
        username: values.username,
        password: values.password,
        nom: values.nom,
        prenom: values.prenom,
        email: values.email,
        telephone: values.telephone || undefined,
      });
      success('Compte créé', fr.auth.accountPending);
      navigate('/login', { replace: true });
    } catch {
      /* error rendered below */
    }
  };

  const signupError = signupMutation.isError ? signupMutation.error : null;

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-cream via-background to-sand-200 px-4 py-12">
      <Card className="w-full max-w-2xl border-border bg-card shadow-xl">
        <CardHeader className="text-center">
          <CardTitle className="font-serif text-2xl text-forest">{fr.auth.signupTab}</CardTitle>
          <CardDescription>{fr.auth.accountInfo}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={handleSubmit(onSubmit)}>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="username" required>
                  {fr.auth.username}
                </Label>
                <Input
                  id="username"
                  autoComplete="username"
                  hasError={Boolean(errors.username)}
                  {...register('username')}
                />
                {errors.username && (
                  <p className="text-xs text-destructive">{errors.username.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" required>
                  {fr.auth.password}
                </Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  hasError={Boolean(errors.password)}
                  {...register('password')}
                />
                {errors.password && (
                  <p className="text-xs text-destructive">{errors.password.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword" required>
                  {fr.auth.confirmPassword}
                </Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  hasError={Boolean(errors.confirmPassword)}
                  {...register('confirmPassword')}
                />
                {errors.confirmPassword && (
                  <p className="text-xs text-destructive">{errors.confirmPassword.message}</p>
                )}
              </div>
            </div>

            <div className="md:col-span-2">
              <PasswordStrengthMeter password={password} />
            </div>

            {/* Le rôle n'est plus choisi à l'inscription : le serveur crée
                systématiquement un compte Bénévole, qu'un Super Admin promeut
                ensuite s'il y a lieu. Laisser le champ donnait l'illusion d'un
                choix et exposait une escalade de privilèges. */}
            <p className="md:col-span-2 text-sm text-muted-foreground">
              {fr.auth.roleAssignedByAdmin}
            </p>

            <p className="text-sm font-medium text-muted-foreground pt-2">
              {fr.auth.personalInfo}
            </p>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="nom" required>
                  {fr.auth.nom}
                </Label>
                <Input id="nom" hasError={Boolean(errors.nom)} {...register('nom')} />
                {errors.nom && <p className="text-xs text-destructive">{errors.nom.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="prenom" required>
                  {fr.auth.prenom}
                </Label>
                <Input id="prenom" hasError={Boolean(errors.prenom)} {...register('prenom')} />
                {errors.prenom && (
                  <p className="text-xs text-destructive">{errors.prenom.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="email" required>
                  {fr.auth.email}
                </Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  hasError={Boolean(errors.email)}
                  {...register('email')}
                />
                {errors.email && (
                  <p className="text-xs text-destructive">{errors.email.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="telephone">{fr.auth.telephone}</Label>
                <Input id="telephone" type="tel" {...register('telephone')} />
              </div>
            </div>

            {signupError && (
              <ErrorAlert
                error={signupError}
                title="Création du compte refusée"
              />
            )}

            <Button type="submit" fullWidth loading={isSubmitting || signupMutation.isPending}>
              {fr.auth.signup}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Déjà un compte ?{' '}
            <Link to="/login" className="font-medium text-primary hover:underline">
              {fr.auth.loginTab}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
