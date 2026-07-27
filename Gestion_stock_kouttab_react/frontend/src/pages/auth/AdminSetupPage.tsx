import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { PasswordStrengthMeter } from '@/components/forms/PasswordStrengthMeter';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useAdminSetup, useValidateInvitation } from '@/api/endpoints/auth';
import { adminSetupSchema, type AdminSetupFormValues } from '@/lib/schemas/auth';
import { fr } from '@/lib/i18n/fr';
import { useToast } from '@/hooks/useToast';

export function AdminSetupPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { success } = useToast();
  const token = params.get('token');
  const email = params.get('email');

  const validation = useValidateInvitation(token, email);
  const setupMutation = useAdminSetup();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<AdminSetupFormValues>({
    resolver: zodResolver(adminSetupSchema),
    defaultValues: { username: '', password: '', confirmPassword: '' },
  });

  const password = watch('password');

  if (!token || !email) {
    return <Navigate to="/login" replace />;
  }

  const onSubmit = async (values: AdminSetupFormValues) => {
    try {
      await setupMutation.mutateAsync({
        token,
        email,
        username: values.username,
        password: values.password,
      });
      success('Compte Super Admin créé', 'Vous êtes maintenant connecté.');
      navigate('/dashboard', { replace: true });
    } catch {
      /* shown below */
    }
  };

  const setupError = setupMutation.isError ? setupMutation.error : null;
  const validationError = validation.isError ? validation.error : null;

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-cream via-background to-sand-200 px-4 py-12">
      <Card className="w-full max-w-md border-border bg-card shadow-xl">
        <CardHeader>
          <CardTitle className="font-serif text-2xl text-forest">
            {fr.auth.adminSetupTitle}
          </CardTitle>
          <CardDescription>{fr.auth.adminSetupSubtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          {validation.isLoading ? (
            <LoadingSpinner label="Vérification de l'invitation…" />
          ) : validationError ? (
            <ErrorAlert
              error={validationError}
              fallback="Lien d'invitation invalide ou expiré."
              title="Invitation invalide"
            />
          ) : (
            <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
              <div className="space-y-1.5">
                <Label>Email</Label>
                <Input value={email} disabled />
              </div>
              <div className="space-y-1.5">
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
              <PasswordStrengthMeter password={password} />
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

              {setupError && <ErrorAlert error={setupError} title="Création refusée" />}

              <Button type="submit" fullWidth loading={isSubmitting || setupMutation.isPending}>
                Créer mon compte Super Admin
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
