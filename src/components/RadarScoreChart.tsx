import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import type { Company, Scores, ScoreKey } from '../types'
import { scoreLabels } from './ScoreBar'

interface RadarScoreChartProps {
  scores?: Scores
  companies?: Company[]
  height?: number
}

const colors = ['#007AFF', '#5856D6', '#FF9F0A', '#AF52DE', '#FF375F']
const keys: ScoreKey[] = [
  'growth',
  'profitability',
  'safety',
  'cashGeneration',
  'valuation',
]

export default function RadarScoreChart({
  scores,
  companies = [],
  height = 280,
}: RadarScoreChartProps) {
  const data = keys.map((key) => ({
    subject: scoreLabels[key],
    ...(scores ? { score: Math.round(scores[key]) } : {}),
    ...Object.fromEntries(
      companies.map((company, index) => [
        `series${index}`,
        Math.round(company.scores[key]),
      ]),
    ),
    fullMark: 100,
  }))

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="68%" accessibilityLayer={false}>
          <PolarGrid stroke="rgba(60,60,67,0.16)" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#636366', fontSize: 11 }}
          />
          <PolarRadiusAxis
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'rgba(255,255,255,0.96)',
              color: '#1C1C1E',
              border: '1px solid rgba(60,60,67,0.14)',
              borderRadius: 14,
              boxShadow: '0 12px 32px rgba(31,38,55,0.12)',
              fontSize: 12,
            }}
          />
          {scores && (
            <Radar
              name="スコア"
              dataKey="score"
              stroke="#007AFF"
              fill="#007AFF"
              fillOpacity={0.22}
              strokeWidth={2}
              isAnimationActive
              animationBegin={100}
              animationDuration={720}
              animationEasing="ease-out"
            />
          )}
          {companies.map((company, index) => (
            <Radar
              key={company.id}
              name={company.name}
              dataKey={`series${index}`}
              stroke={colors[index]}
              fill={colors[index]}
              fillOpacity={index === 0 ? 0.13 : 0.04}
              strokeWidth={2}
              isAnimationActive
              animationBegin={100 + index * 70}
              animationDuration={720}
              animationEasing="ease-out"
            />
          ))}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
