import { STAT_LABEL, STAT_ORDER, typeZh } from '@/utils/constants'
import EChart from './EChart'

/** 各属性的六维均值分组柱 */
export default function TypeStatsBarChart({ items = [], loading }) {
  const colors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2']
  return (
    <EChart
      loading={loading}
      height={400}
      option={{
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0, itemWidth: 10, itemHeight: 10 },
        grid: { left: 55, right: 25, top: 30, bottom: 80 },
        xAxis: {
          type: 'category',
          data: items.map((d) => typeZh(d.type)),
          axisLabel: { rotate: 40, interval: 0 },
        },
        yAxis: { type: 'value', name: '均值' },
        series: STAT_ORDER.map((key, i) => ({
          name: STAT_LABEL[key],
          type: 'bar',
          barMaxWidth: 14,
          itemStyle: { color: colors[i % colors.length] },
          data: items.map((d) => Math.round(d[key] ?? 0)),
        })),
      }}
    />
  )
}
