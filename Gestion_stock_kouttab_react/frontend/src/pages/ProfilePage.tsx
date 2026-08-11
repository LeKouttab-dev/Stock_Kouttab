import { ProfileForm } from '@/components/forms/ProfileForm';
import { UserRound } from 'lucide-react';
import { fr } from '@/lib/i18n/fr';

export function ProfilePage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <UserRound className="h-6 w-6" aria-hidden />
          {fr.nav.profile}
        </h1>
        <p className="text-sm text-muted-foreground">Vos informations personnelles.</p>
      </div>

      <ProfileForm />
    </div>
  );
}
