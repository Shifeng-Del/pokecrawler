import { STAT_LABEL, STAT_ORDER, normalizeStats, typeColor } from '@/utils/constants'
import EChart from './EChart'

const PALETTE = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1']

/** 多只宝可梦的六维能力对比 */
export default function AbilityRadarChart({ items = [], loading }) {
  const series = items.map((p, i) => {
    const stats = normalizeStats(p.stats)
    return {
      value: STAT_ORDER.map((k) => stats[k] ?? 0),
      name: `${p.name_zh || p.name} (#${p.id})`,
      itemStyle: { color: PALETTE[i % PALETTE.length] },
      areaStyle: { opacity: 0.15 },
    }
  })

  return (
    <EChart
      loading={loading}
      height={380}
      option={{
        tooltip: {},
        legend: { bottom: 0, itemWidth: 12, itemHeight: 12 },
        radar: {
          indicator: STAT_ORDER.map((k) => ({ name: STAT_LABEL[k], max: 180 })),
          radius: '65%',
          splitArea: { areaStyle: { color: ['#fafafa', '#f0f5ff'] } },
        },
        series: [{ type: 'radar', data: series }],
      }}
    />
  )
}
