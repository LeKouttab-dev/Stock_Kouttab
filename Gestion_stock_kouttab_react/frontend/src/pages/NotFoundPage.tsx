import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { fr } from '@/lib/i18n/fr';

export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-full items-center justify-center px-6 py-12">
      <div className="text-center space-y-4">
        <p className="text-7xl font-bold text-primary">404</p>
        <h1 className="text-2xl font-bold">{fr.common.notFoundTitle}</h1>
        <p className="text-muted-foreground">{fr.common.notFoundText}</p>
        <Button onClick={() => navigate('/dashboard')}>{fr.common.goHome}</Button>
      </div>
    </div>
  );
}
