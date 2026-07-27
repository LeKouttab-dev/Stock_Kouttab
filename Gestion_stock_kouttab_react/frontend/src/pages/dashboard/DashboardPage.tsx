import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { OverviewTab } from './tabs/OverviewTab';
import { HistoryTab } from './tabs/HistoryTab';
import { AlertsTab } from './tabs/AlertsTab';
import { ModificationsTab } from './tabs/ModificationsTab';
import { fr } from '@/lib/i18n/fr';

export function DashboardPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-2xl font-bold text-forest">{fr.dashboard.title}</h1>
        <p className="text-sm text-muted-foreground">
          Vue synthétique du stock, alertes et historique des modifications.
        </p>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="grid w-full grid-cols-2 sm:grid-cols-4">
          <TabsTrigger value="overview">📈 {fr.dashboard.overview}</TabsTrigger>
          <TabsTrigger value="history">📝 {fr.dashboard.history}</TabsTrigger>
          <TabsTrigger value="alerts">⚠️ {fr.dashboard.alerts}</TabsTrigger>
          <TabsTrigger value="modifications">🔄 {fr.dashboard.modifications}</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab />
        </TabsContent>
        <TabsContent value="history">
          <HistoryTab />
        </TabsContent>
        <TabsContent value="alerts">
          <AlertsTab />
        </TabsContent>
        <TabsContent value="modifications">
          <ModificationsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
