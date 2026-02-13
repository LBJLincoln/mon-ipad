interface TypingIndicatorProps {
  color?: string
}

export function TypingIndicator({ color = 'var(--tx3)' }: TypingIndicatorProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center"
        style={{ backgroundColor: `${color}10` }}
      >
        <div className="flex gap-[3px]">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-[5px] h-[5px] rounded-full"
              style={{
                backgroundColor: color,
                animation: `typing 1.4s ease-in-out ${i * 0.2}s infinite`,
              }}
            />
          ))}
        </div>
      </div>
      <span className="text-[12px] text-tx3">Recherche en cours...</span>
    </div>
  )
}
