import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react';
import type { OrderStatus } from '../types';

export function cn(...values: ClassValue[]) {
  return twMerge(clsx(values));
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'quiet' | 'danger';
  icon?: ReactNode;
}

export function Button({ variant = 'secondary', icon, className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition duration-200 disabled:pointer-events-none disabled:opacity-45',
        variant === 'primary' && 'bg-accent text-[#211106] hover:bg-accent-light',
        variant === 'secondary' && 'border border-line bg-panel text-foreground hover:border-muted hover:bg-panel-hover',
        variant === 'quiet' && 'text-muted hover:bg-panel-hover hover:text-foreground',
        variant === 'danger' && 'border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/15',
        className,
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn('rounded-2xl border border-line bg-card p-5 shadow-card sm:p-6', className)}>{children}</section>;
}

const statusClass: Record<OrderStatus, string> = {
  Pending: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
  'In Production': 'border-accent/20 bg-accent/10 text-accent-light',
  Shipped: 'border-sky-400/20 bg-sky-400/10 text-sky-300',
  Delivered: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
};

const statusLabel: Record<OrderStatus, string> = {
  Pending: 'Ожидает',
  'In Production': 'В производстве',
  Shipped: 'Отправлен',
  Delivered: 'Доставлен',
};

export function Badge({ status }: { status: OrderStatus }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-bold', statusClass[status])}>
      <span className="size-1.5 rounded-full bg-current" />
      {statusLabel[status]}
    </span>
  );
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: { value: string; label: string }[];
}

export function Select({ label, options, className, ...props }: SelectProps) {
  return (
    <label className="flex min-w-0 flex-col gap-2 text-sm font-semibold text-muted">
      {label}
      <select
        className={cn('min-h-11 w-full rounded-xl border border-line bg-app-bg px-3 text-sm text-foreground outline-none transition focus:border-accent', className)}
        {...props}
      >
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span aria-label="Загрузка" className={cn('inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent', className)} />;
}
