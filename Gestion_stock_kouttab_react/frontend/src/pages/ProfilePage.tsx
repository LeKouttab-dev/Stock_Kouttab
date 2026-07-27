import { ProfileForm } from '@/components/forms/ProfileForm';
import { fr } from '@/lib/i18n/fr';

export function ProfilePage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">👤 {fr.nav.profile}</h1>
        <p className="text-sm text-muted-foreground">Vos informations personnelles.</p>
      </div>

      <ProfileForm />
    </div>
  );
}
