interface BadgeProps {
  children: React.ReactNode
  color?: string
  className?: string
  onClick?: () => void
}

export function Badge({ children, color = 'var(--ac)', className = '', onClick }: BadgeProps) {
  return (
    <span
      onClick={onClick}
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full cursor-pointer transition-all hover:scale-105 ${className}`}
      style={{
        backgroundColor: `${color}15`,
        color,
        border: `1px solid ${color}25`,
      }}
    >
      {children}
    </span>
  )
}
