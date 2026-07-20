import { cn } from '@/lib/utils'

interface BadgeProps {
  variant?: 'default' | 'secondary' | 'outline' | 'destructive' | 'success'
  children: React.ReactNode
  className?: string
}

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
        {
          'bg-primary text-primary-foreground hover:bg-primary/80': variant === 'default',
          'bg-secondary text-secondary-foreground hover:bg-secondary/80': variant === 'secondary',
          'border border-input text-foreground': variant === 'outline',
          'bg-destructive text-destructive-foreground hover:bg-destructive/80': variant === 'destructive',
          'bg-green-500 text-white hover:bg-green-500/80': variant === 'success',
        },
        className
      )}
    >
      {children}
    </span>
  )
}
