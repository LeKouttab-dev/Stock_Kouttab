import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, CircleCheck, TriangleAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { PasswordInput } from '@/components/ui/password-input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { PasswordStrengthMeter } from '@/components/forms/PasswordStrengthMeter';
import { useResetPassword, useResetTokenValidity } from '@/api/endpoints/auth';
import { resetPasswordSchema, type ResetPasswordFormValues } from '@/lib/schemas/auth';
import { Logo } from '@/components/shared/Logo';
import { fr } from '@/lib/i18n/fr';

/**
 * Choix d'un nouveau mot de passe depuis le lien reçu par courriel.
 *
 * Le lien est pré-vérifié avant d'afficher le formulaire : faire saisir deux
 * fois un mot de passe pour découvrir ensuite que le jeton a expiré est une
 * perte de temps inutile.
 */
export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const [termine, setTermine] = useState(false);

  const validite = useResetTokenValidity(token);
  const reinitialiser = useResetPassword();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: '', confirmPassword: '' },
  });

  const onSubmit = (values: ResetPasswordFormValues) => {
    if (!token) return;
    reinitialiser.mutate(
      { token, password: values.password },
      { onSuccess: () => setTermine(true) },
    );
  };

  const lienInvalide = !token || (validite.isFetched && validite.data?.valid === false);

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-cream via-background to-sand-200 px-4 py-12">
      <Card className="w-full max-w-md border-border bg-card shadow-xl">
        <CardHeader className="space-y-2 text-center">
          <Logo className="mx-auto h-16 w-16 rounded-full shadow-md" />
          <CardTitle className="font-serif text-2xl text-forest">{fr.auth.resetTitle}</CardTitle>
          {!termine && !lienInvalide && (
            <CardDescription>{fr.auth.passwordRequirements}</CardDescription>
          )}
        </CardHeader>

        <CardContent>
          {termine ? (
            <Alert variant="success">
              <CircleCheck className="h-4 w-4" />
              <AlertDescription>{fr.auth.resetDone}</AlertDescription>
            </Alert>
          ) : lienInvalide ? (
            <Alert variant="destructive">
              <TriangleAlert className="h-4 w-4" />
              <AlertDescription>{fr.auth.resetInvalid}</AlertDescription>
            </Alert>
          ) : validite.isLoading ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              <LoadingSpinner />
              {fr.auth.resetChecking}
            </div>
          ) : (
            <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
              <div className="space-y-1.5">
                <Label htmlFor="password" required>
                  {fr.auth.password}
                </Label>
                <PasswordInput
                  id="password"
                  autoComplete="new-password"
                  hasError={Boolean(errors.password)}
                  {...register('password')}
                />
                {errors.password && (
                  <p className="text-xs text-destructive">{errors.password.message}</p>
                )}
                <PasswordStrengthMeter password={watch('password') ?? ''} />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword" required>
                  {fr.auth.confirmPassword}
                </Label>
                <PasswordInput
                  id="confirmPassword"
                  autoComplete="new-password"
                  hasError={Boolean(errors.confirmPassword)}
                  {...register('confirmPassword')}
                />
                {errors.confirmPassword && (
                  <p className="text-xs text-destructive">{errors.confirmPassword.message}</p>
                )}
              </div>

              <Button type="submit" fullWidth loading={reinitialiser.isPending}>
                {fr.auth.resetSubmit}
              </Button>
            </form>
          )}

          <p className="mt-6 text-center text-sm">
            <Link
              to="/login"
              className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              {fr.auth.backToLogin}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
