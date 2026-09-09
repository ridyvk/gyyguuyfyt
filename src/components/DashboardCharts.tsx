import { memo } from 'react'
import { Layers3 } from 'lucide-react'
import { useReducedMotion } from '../lib/useReducedMotion'
import ChartReveal from './ChartReveal'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const themePalette = [
  { from: '#8fae9d', to: '#66907a' },
  { from: '#a5bed0', to: '#7b9fb8' },
  { from: '#baafd1', to: '#998ab3' },
  { from: '#d9baa8', to: '#bd9480' },
  { from: '#dfce9b', to: '#bda86a' },
]


interface Props { industryData: { name: string; value: number }[]; themeData: { name: string; value: number }[] }
function DashboardCharts({ industryData, themeData }: Props) {
  const reducedMotion = useReducedMotion()
  return <div className="dashboard-chart-grid">
        <article className="panel panel--wide">
          <div className="panel__heading">
            <div><h2>業種別企業数 上位12業種</h2></div>
            <Layers3 size={20} />
          </div>
          <div className="chart-wrap chart-wrap--bar">
            <ChartReveal className="chart-reveal--bar">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={industryData}
                  layout="vertical"
                  margin={{ left: 0, right: 16, top: 5, bottom: 0 }}
                  accessibilityLayer={false}
                >
                  <defs>
                    <linearGradient id="industryBarGradient" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#76a28a" stopOpacity={0.92} />
                      <stop offset="62%" stopColor="#aac8b5" stopOpacity={0.68} />
                      <stop offset="100%" stopColor="#e0eade" stopOpacity={0.38} />
                    </linearGradient>
                    <filter id="industryBarShadow" x="-40%" y="-20%" width="180%" height="150%">
                      <feDropShadow dx="0" dy="5" stdDeviation="5" floodColor="#76a28a" floodOpacity="0.14" />
                    </filter>
                  </defs>
                  <CartesianGrid
                    horizontal={false}
                    stroke="rgba(88, 116, 136, 0.11)"
                    strokeDasharray="2 8"
                  />
                  <XAxis
                    type="number"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#6c7d70', fontSize: 12 }}
                    allowDecimals={false}
                    tickMargin={9}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={110}
                    interval={0}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#627367', fontSize: 12 }}
                    tickMargin={8}
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(91, 174, 219, 0.055)' }}
                    contentStyle={{
                      backdropFilter: 'blur(18px)',
                      background: 'rgba(255,255,255,0.84)',
                      color: '#25333B',
                      border: '1px solid rgba(104,148,174,0.16)',
                      borderRadius: 13,
                      boxShadow: '0 14px 35px rgba(44,79,99,0.12)',
                    }}
                  />
                  <Bar
                    dataKey="value"
                    name="企業数"
                    fill="url(#industryBarGradient)"
                    radius={[5, 5, 5, 5]}
                    barSize={14}
                    style={{ filter: 'url(#industryBarShadow)' }}
                    isAnimationActive={!reducedMotion}
                    animationBegin={80}
                    animationDuration={860}
                    animationEasing="ease-out"
                  />
                </BarChart>
              </ResponsiveContainer>
            </ChartReveal>
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div><h2>注目テーマ</h2></div>
          </div>
          <div className="theme-chart">
            <div className="theme-chart__donut">
              <ChartReveal className="chart-reveal--pie">
                <ResponsiveContainer width="100%" height={190}>
                  <PieChart accessibilityLayer={false}>
                    <defs>
                      {themePalette.map((color, index) => (
                        <linearGradient
                          id={`themeGradient${index}`}
                          key={color.from}
                          x1="0"
                          y1="0"
                          x2="1"
                          y2="1"
                        >
                          <stop offset="0%" stopColor={color.from} stopOpacity={0.9} />
                          <stop offset="100%" stopColor={color.to} stopOpacity={0.72} />
                        </linearGradient>
                      ))}
                    </defs>
                    <Pie
                      data={themeData.slice(0, 5)}
                      innerRadius={60}
                      outerRadius={76}
                      paddingAngle={4}
                      cornerRadius={7}
                      dataKey="value"
                      startAngle={90}
                      endAngle={-270}
                      stroke="rgba(255,255,255,0.88)"
                      strokeWidth={2}
                      isAnimationActive={!reducedMotion}
                      animationBegin={80}
                      animationDuration={920}
                      animationEasing="ease-out"
                    >
                      {themeData.slice(0, 5).map((entry, index) => (
                        <Cell
                          key={entry.name}
                          fill={`url(#themeGradient${index})`}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backdropFilter: 'blur(18px)',
                        background: 'rgba(255,255,255,0.84)',
                        color: '#25333B',
                        border: '1px solid rgba(104,148,174,0.16)',
                        borderRadius: 13,
                        boxShadow: '0 14px 35px rgba(44,79,99,0.12)',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </ChartReveal>
              <div className="theme-chart__center" aria-hidden="true">
                <small>テーマ</small>
                <strong>5</strong>
              </div>
            </div>
            <div className="theme-list">
              {themeData.slice(0, 5).map((theme, index) => (
                <div key={theme.name}>
                  <i
                    style={{
                      background: `linear-gradient(135deg, ${themePalette[index].from}, ${themePalette[index].to})`,
                      boxShadow: `0 0 0 4px ${themePalette[index].from}18`,
                    }}
                  />
                  <span>{theme.name}</span>
                  <strong>{theme.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </article>

  </div>
}
export default memo(DashboardCharts)
