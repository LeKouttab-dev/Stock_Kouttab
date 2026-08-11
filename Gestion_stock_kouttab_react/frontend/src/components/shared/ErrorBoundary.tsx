import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Filet de sécurité contre les écrans blancs.
 *
 * Sans elle, une exception de rendu démonte tout l'arbre React et l'utilisateur
 * se retrouve devant une page vide, sans message ni moyen de repartir — le tout
 * sans qu'aucune trace ne remonte.
 *
 * Doit rester une classe : React ne propose pas d'équivalent en composant
 * fonctionnel pour `componentDidCatch`.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Volontairement conservé en production : c'est la seule trace disponible
    // quand un utilisateur signale « la page est blanche ».
    console.error('Erreur de rendu non rattrapée :', error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center">
        <div className="space-y-2">
          <h1 className="text-xl font-bold">Une erreur inattendue est survenue</h1>
          <p className="max-w-md text-sm text-muted-foreground">
            L&apos;affichage de cette page a échoué. Vos données ne sont pas perdues. Réessayez, et
            signalez le problème s&apos;il persiste.
          </p>
        </div>

        <div className="flex gap-2">
          <Button onClick={this.handleReset}>Réessayer</Button>
          <Button variant="outline" onClick={() => window.location.assign('/dashboard')}>
            Retour au tableau de bord
          </Button>
        </div>

        {/* Le détail technique n'est montré qu'en développement : en production
            il n'aiderait pas l'utilisateur et exposerait la structure interne. */}
        {import.meta.env.DEV && (
          <pre className="max-w-full overflow-auto rounded-md bg-muted p-3 text-left text-xs">
            {error.stack ?? error.message}
          </pre>
        )}
      </div>
    );
  }
}
