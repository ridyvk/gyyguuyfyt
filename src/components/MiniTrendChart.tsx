import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from 'recharts'

interface MiniTrendChartProps {
  data: number[]
  color?: string
  height?: number
  showTooltip?: boolean
}

export default function MiniTrendChart({
  data,
  color = '#007AFF',
  height = 48,
  showTooltip = false,
}: MiniTrendChartProps) {
  if (data.length === 0) {
    return <div className="mini-trend-empty" style={{ height }}>データなし</div>
  }
  const chartData = data.map((value, index) => ({ index, value }))
  const domain = [
    Math.min(...data) - Math.abs(Math.min(...data)) * 0.08 - 0.5,
    Math.max(...data) + Math.abs(Math.max(...data)) * 0.08 + 0.5,
  ]

  return (
    <div style={{ width: '100%', height }} aria-hidden={!showTooltip}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 4, right: 2, bottom: 2, left: 2 }}
          accessibilityLayer={false}
        >
          <defs>
            <linearGradient id={`mini-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.32} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={domain} />
          {showTooltip && (
            <Tooltip
              contentStyle={{
                background: 'rgba(255,255,255,0.96)',
                color: '#1C1C1E',
                border: '1px solid rgba(60,60,67,0.14)',
                borderRadius: 12,
                boxShadow: '0 10px 28px rgba(31,38,55,0.12)',
                fontSize: 12,
              }}
              labelFormatter={() => ''}
            />
          )}
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#mini-${color.replace('#', '')})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
