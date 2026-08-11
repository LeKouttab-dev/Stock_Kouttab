import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { History, RefreshCw, TrendingUp, TriangleAlert } from 'lucide-react';
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
          <TabsTrigger value="overview" className="gap-1.5">
            <TrendingUp className="h-4 w-4" aria-hidden />
            {fr.dashboard.overview}
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-1.5">
            <History className="h-4 w-4" aria-hidden />
            {fr.dashboard.history}
          </TabsTrigger>
          <TabsTrigger value="alerts" className="gap-1.5">
            <TriangleAlert className="h-4 w-4" aria-hidden />
            {fr.dashboard.alerts}
          </TabsTrigger>
          <TabsTrigger value="modifications" className="gap-1.5">
            <RefreshCw className="h-4 w-4" aria-hidden />
            {fr.dashboard.modifications}
          </TabsTrigger>
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
