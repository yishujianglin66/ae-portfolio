import React from 'react'
import { cn } from '@/lib/utils'

interface TabsProps {
  children: React.ReactNode
  value: string
  onValueChange: (value: string) => void
}

export function Tabs({ children, value, onValueChange }: TabsProps) {
  return (
    <div className="flex flex-col">
      <div className="flex border-b">
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child)) {
            return React.cloneElement(child as React.ReactElement<TabTriggerProps>, {
              value,
              onValueChange,
            })
          }
          return child
        })}
      </div>
      <div className="mt-2">
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child) && (child as React.ReactElement).type === TabContent) {
            return React.cloneElement(child as React.ReactElement<TabContentProps>, {
              value,
            })
          }
          if (React.isValidElement(child) && (child as React.ReactElement).type !== TabTrigger) {
            return child
          }
          return null
        })}
      </div>
    </div>
  )
}

interface TabTriggerProps {
  value: string
  children: React.ReactNode
  onValueChange: (value: string) => void
}

export function TabTrigger({ value, children, onValueChange }: TabTriggerProps) {
  const triggerValue = (children as string).toLowerCase().replace(/\s+/g, '-')
  const isActive = value === triggerValue

  return (
    <button
      onClick={() => onValueChange(triggerValue)}
      className={cn(
        'px-4 py-2 text-sm font-medium transition-colors relative',
        isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
      {isActive && (
        <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
      )}
    </button>
  )
}

interface TabContentProps {
  value: string
  children: React.ReactNode
}

export function TabContent({ value, children }: TabContentProps) {
  const contentValue = (children as string).toLowerCase().replace(/\s+/g, '-')
  return value === contentValue ? <>{children}</> : null
}
