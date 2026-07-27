import { useEffect } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Lock, User as UserIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorAlert } from '@/components/shared/ErrorAlert';
import { useLogin } from '@/api/endpoints/auth';
import { loginSchema, type LoginFormValues } from '@/lib/schemas/auth';
import { useAuth } from '@/hooks/useAuth';
import { fr } from '@/lib/i18n/fr';
import { useToast } from '@/hooks/useToast';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const loginMutation = useLogin();
  const { success } = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '' },
  });

  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, location.state, navigate]);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const onSubmit = async (values: LoginFormValues) => {
    try {
      await loginMutation.mutateAsync(values);
      success('Connexion réussie', 'Bienvenue !');
      const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
      navigate(from, { replace: true });
    } catch {
      /* error rendered below */
    }
  };

  const loginError = loginMutation.isError ? loginMutation.error : null;

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-cream via-background to-sand-200 px-4 py-12">
      <Card className="w-full max-w-md border-border bg-card shadow-xl">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-terracotta font-serif text-2xl font-bold text-cream-50 shadow-md">
            K
          </div>
          <CardTitle className="font-serif text-2xl text-forest">{fr.app.title}</CardTitle>
          <CardDescription>{fr.auth.loginTitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-1.5">
              <Label htmlFor="username" required>
                {fr.auth.username}
              </Label>
              <div className="relative">
                <UserIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="username"
                  type="text"
                  autoComplete="username"
                  className="pl-10"
                  hasError={Boolean(errors.username)}
                  {...register('username')}
                />
              </div>
              {errors.username && (
                <p className="text-xs text-destructive">{errors.username.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" required>
                {fr.auth.password}
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  className="pl-10"
                  hasError={Boolean(errors.password)}
                  {...register('password')}
                />
              </div>
              {errors.password && (
                <p className="text-xs text-destructive">{errors.password.message}</p>
              )}
            </div>

            {loginError && (
              <ErrorAlert error={loginError} title="Connexion refusée" />
            )}

            <Button
              type="submit"
              fullWidth
              loading={isSubmitting || loginMutation.isPending}
            >
              {fr.auth.login}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Pas encore de compte ?{' '}
            <Link to="/signup" className="font-medium text-primary hover:underline">
              {fr.auth.signupTab}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
