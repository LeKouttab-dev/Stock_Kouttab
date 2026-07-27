import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ChevronDown, ChevronRight, Copy, Trash2, Download } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { EmptyState } from '@/components/shared/EmptyState';
import { StatusBadge } from '@/components/shared/StatusBadge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useAllExpenses,
  useDeleteExpense,
  useValidateExpense,
  getExpenseFileUrl,
} from '@/api/endpoints/expenses';
import { expenseValidateSchema, type ExpenseValidateFormValues } from '@/lib/schemas/expense';
import { EXPENSE_STATUS } from '@/lib/constants';
import type { Expense } from '@/types/api';
import { copyToClipboard } from '@/lib/utils';
import { useToast } from '@/hooks/useToast';
import { extractErrorMessage } from '@/api/client';
import { formatCurrency, formatDate } from '@/lib/format';
import { fr } from '@/lib/i18n/fr';

export function ValidateExpensesPage() {
  const { data: expenses = [], isLoading } = useAllExpenses();
  const [expanded, setExpanded] = useState<number | null>(null);

  if (isLoading) return <LoadingSpinner fullPage />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">📝 {fr.expenses.dashboardCompta}</h1>
        <p className="text-sm text-muted-foreground">Validation et remboursement des notes.</p>
      </div>

      {expenses.length === 0 ? (
        <EmptyState title={fr.expenses.aucuneATraiter} />
      ) : (
        <div className="space-y-3">
          {expenses.map((exp) => {
            const total = exp.montant - exp.remboursement_deja_emis - exp.remise;
            const isOpen = expanded === exp.id;
            return (
              <Card key={exp.id}>
                <CardContent className="p-0">
                  <button
                    onClick={() => setExpanded(isOpen ? null : exp.id)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/30"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      )}
                      <span className="font-medium truncate">
                        {formatDate(exp.date_depense)} — {exp.user_full_name ?? '—'} —{' '}
                        {formatCurrency(total)}
                      </span>
                    </div>
                    <StatusBadge status={exp.status} />
                  </button>
                  {isOpen && <ValidateExpenseDetail expense={exp} total={total} />}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

interface DetailProps {
  expense: Expense;
  total: number;
}

function ValidateExpenseDetail({ expense, total }: DetailProps) {
  const validate = useValidateExpense();
  const remove = useDeleteExpense();
  const toast = useToast();

  const form = useForm<ExpenseValidateFormValues>({
    resolver: zodResolver(expenseValidateSchema),
    defaultValues: {
      status: expense.status,
      commentaires_compta: expense.commentaires_compta ?? '',
    },
  });

  const onValidate = async (values: ExpenseValidateFormValues) => {
    try {
      await validate.mutateAsync({
        id: expense.id,
        payload: { status: values.status, commentaires_compta: values.commentaires_compta },
      });
      toast.success(fr.expenses.noteUpdated);
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  const onCopyRib = async () => {
    if (!expense.user_rib) return;
    await copyToClipboard(expense.user_rib);
    toast.success(fr.expenses.ribCopie);
  };

  const onDelete = async () => {
    if (!confirm(fr.expenses.suppressionWarning)) return;
    try {
      await remove.mutateAsync(expense.id);
      toast.success(fr.expenses.noteSupprimee);
    } catch (e) {
      toast.error('Erreur', extractErrorMessage(e));
    }
  };

  return (
    <div className="border-t bg-muted/10 px-4 py-4 space-y-4 text-sm">
      <div className="grid gap-2 md:grid-cols-2">
        <p>
          <strong>Rattachement :</strong> {expense.rattachement}
        </p>
        <p>
          <strong>Fournisseur :</strong> {expense.fournisseur ?? '—'}
        </p>
        <p>
          <strong>Nature :</strong> {expense.nature_charge ?? '—'}
        </p>
        <p>
          <strong>{fr.expenses.commentaireUtilisateur} :</strong> {expense.commentaires ?? '—'}
        </p>
      </div>

      <div className="rounded-md border bg-background px-3 py-2 space-y-1">
        <p>
          {fr.expenses.montantBrut} : <strong>{formatCurrency(expense.montant)}</strong>
        </p>
        <p>
          Remboursement déjà émis : <strong>-{formatCurrency(expense.remboursement_deja_emis)}</strong>
        </p>
        <p>
          Remise : <strong>-{formatCurrency(expense.remise)}</strong>
        </p>
        <p className="text-base">
          {fr.expenses.totalARembourser} : <strong>{formatCurrency(total)}</strong>
        </p>
      </div>

      {expense.user_rib ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <Label>{fr.expenses.ribUtilisateur}</Label>
            <Input value={expense.user_rib} disabled />
          </div>
          <Button variant="outline" onClick={onCopyRib}>
            <Copy className="h-4 w-4" />
            {fr.expenses.copierRib}
          </Button>
        </div>
      ) : (
        <Alert variant="warning">
          <AlertDescription>{fr.expenses.ribAbsent}</AlertDescription>
        </Alert>
      )}

      {expense.files && expense.files.length > 0 ? (
        <div className="space-y-1">
          <p className="font-medium">Justificatifs :</p>
          <ul className="space-y-1">
            {expense.files.map((f) => (
              <li key={f.id}>
                <a
                  href={getExpenseFileUrl(expense.id, f.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <Download className="h-3.5 w-3.5" />
                  {f.nom_fichier}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <Alert variant="warning">
          <AlertDescription>{fr.expenses.aucunTicket}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={form.handleSubmit(onValidate)} className="space-y-3 rounded-md border bg-background p-3">
        <div>
          <Label>{fr.expenses.commentaireCompta}</Label>
          <Textarea rows={2} {...form.register('commentaires_compta')} />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[200px]">
            <Label>{fr.expenses.changerStatut}</Label>
            <Select
              value={form.watch('status')}
              onValueChange={(v) => form.setValue('status', v as (typeof EXPENSE_STATUS)[number])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EXPENSE_STATUS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" loading={validate.isPending}>
            {fr.common.update}
          </Button>
        </div>
      </form>

      {expense.status === 'Remboursée' && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 space-y-2">
          <p className="text-sm font-semibold">🗑️ {fr.expenses.zoneSuppression}</p>
          <p className="text-xs text-muted-foreground">{fr.expenses.suppressionWarning}</p>
          <Button variant="destructive" size="sm" onClick={onDelete} loading={remove.isPending}>
            <Trash2 className="h-4 w-4" />
            {fr.expenses.supprimer}
          </Button>
        </div>
      )}
    </div>
  );
}
