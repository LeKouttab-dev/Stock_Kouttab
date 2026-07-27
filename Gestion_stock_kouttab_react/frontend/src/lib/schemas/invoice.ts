import { z } from 'zod';
import { INVOICE_STATUS } from '../constants';

export const invoiceUploadSchema = z.object({
  comment: z.string().optional().or(z.literal('')),
});

export type InvoiceUploadFormValues = z.infer<typeof invoiceUploadSchema>;

export const invoiceStatusSchema = z.object({
  status: z.enum(INVOICE_STATUS),
});

export type InvoiceStatusFormValues = z.infer<typeof invoiceStatusSchema>;
