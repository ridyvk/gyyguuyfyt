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
  { from: '#78BEF4', to: '#3A8FD8' },
  { from: '#8DDDD4', to: '#4BAEA9' },
  { from: '#AAA8ED', to: '#7570D4' },
  { from: '#DAB4E8', to: '#AA75C5' },
  { from: '#F4CCA2', to: '#E4A263' },
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
                  margin={{ left: -16, right: 8, top: 14, bottom: 0 }}
                  accessibilityLayer={false}
                >
                  <defs>
                    <linearGradient id="industryBarGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4BA7E7" stopOpacity={0.92} />
                      <stop offset="62%" stopColor="#7FC9EA" stopOpacity={0.68} />
                      <stop offset="100%" stopColor="#B8E6EE" stopOpacity={0.38} />
                    </linearGradient>
                    <filter id="industryBarShadow" x="-40%" y="-20%" width="180%" height="150%">
                      <feDropShadow dx="0" dy="5" stdDeviation="5" floodColor="#4BA7E7" floodOpacity="0.14" />
                    </filter>
                  </defs>
                  <CartesianGrid
                    vertical={false}
                    stroke="rgba(88, 116, 136, 0.11)"
                    strokeDasharray="2 8"
                  />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#87959F', fontSize: 10 }}
                    interval={0}
                    angle={-18}
                    textAnchor="end"
                    height={58}
                    tickMargin={9}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#9AA5AD', fontSize: 10 }}
                    allowDecimals={false}
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
                    radius={[10, 10, 10, 10]}
                    barSize={18}
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
                <ResponsiveContainer width="100%" height={210}>
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
                      innerRadius={66}
                      outerRadius={87}
                      paddingAngle={5}
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
