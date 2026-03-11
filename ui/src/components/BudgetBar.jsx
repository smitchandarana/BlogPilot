export default function BudgetBar({ actionType, count, limit, label }) {
  const pct = limit > 0 ? Math.min((count / limit) * 100, 100) : 0

  const fillColor =
    pct < 60
      ? 'bg-emerald-500'
      : pct < 85
        ? 'bg-amber-400'
        : 'bg-red-500'

  const textColor =
    pct < 60
      ? 'text-emerald-400'
      : pct < 85
        ? 'text-amber-400'
        : 'text-red-400'

  const displayLabel = label || actionType.replace(/_/g, ' ')

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400 capitalize">{displayLabel}</span>
        <span className={`text-xs font-semibold tabular-nums ${textColor}`}>
          {count} / {limit}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
        <div
          className={`h-full rounded-full ${fillColor} transition-[width] duration-500 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
