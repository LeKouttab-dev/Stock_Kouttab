import * as LabelPrimitive from '@radix-ui/react-label';
import { forwardRef, type ComponentPropsWithoutRef } from 'react';
import { cn } from '@/lib/utils';

export const Label = forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  ComponentPropsWithoutRef<typeof LabelPrimitive.Root> & { required?: boolean }
>(({ className, required, children, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      'text-sm font-medium leading-none text-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
      className,
    )}
    {...props}
  >
    {children}
    {required && <span className="ml-0.5 text-destructive">*</span>}
  </LabelPrimitive.Root>
));
Label.displayName = 'Label';
