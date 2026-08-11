import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, MailCheck, User as UserIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useForgotPassword } from '@/api/endpoints/auth';
import { forgotPasswordSchema, type ForgotPasswordFormValues } from '@/lib/schemas/auth';
import { Logo } from '@/components/shared/Logo';
import { fr } from '@/lib/i18n/fr';

/**
 * Demande d'un lien de réinitialisation.
 *
 * L'écran affiche le même message de confirmation dans tous les cas, y compris
 * pour un compte inconnu : le serveur ne révèle jamais si une adresse est
 * enregistrée, et l'interface ne doit pas contredire cette règle.
 */
export function ForgotPasswordPage() {
  const [envoye, setEnvoye] = useState(false);
  const demande = useForgotPassword();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { identifiant: '' },
  });

  const onSubmit = (values: ForgotPasswordFormValues) => {
    demande.mutate(values.identifiant, { onSuccess: () => setEnvoye(true) });
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-cream via-background to-sand-200 px-4 py-12">
      <Card className="w-full max-w-md border-border bg-card shadow-xl">
        <CardHeader className="space-y-2 text-center">
          <Logo className="mx-auto h-16 w-16 rounded-full shadow-md" />
          <CardTitle className="font-serif text-2xl text-forest">{fr.auth.forgotTitle}</CardTitle>
          <CardDescription>{fr.auth.forgotHelp}</CardDescription>
        </CardHeader>

        <CardContent>
          {envoye ? (
            <Alert variant="success">
              <MailCheck className="h-4 w-4" />
              <AlertDescription>{fr.auth.forgotSent}</AlertDescription>
            </Alert>
          ) : (
            <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
              <div className="space-y-1.5">
                <Label htmlFor="identifiant" required>
                  {fr.auth.loginIdentifier}
                </Label>
                <div className="relative">
                  <UserIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="identifiant"
                    type="text"
                    autoComplete="username email"
                    className="pl-10"
                    hasError={Boolean(errors.identifiant)}
                    {...register('identifiant')}
                  />
                </div>
                {errors.identifiant && (
                  <p className="text-xs text-destructive">{errors.identifiant.message}</p>
                )}
              </div>

              <Button type="submit" fullWidth loading={demande.isPending}>
                {fr.auth.forgotSubmit}
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
