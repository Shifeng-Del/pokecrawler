import { TYPE_INFO, typeColor, typeZh, toKg, toMeters } from '@/utils/constants'
import EChart from './EChart'

/** 身高 × 体重 散点：气泡大小=种族值，颜色=属性 */
export default function HeightWeightScatter({ items = [], loading }) {
  const groups = Object.keys(TYPE_INFO)
    .map((type) => ({
      type,
      data: items
        .filter((p) => p.type_primary === type)
        .map((p) => [toMeters(p.height), toKg(p.weight), p.stat_total, p.name_zh || p.name]),
    }))
    .filter((g) => g.data.length)

  return (
    <EChart
      loading={loading}
      height={400}
      option={{
        tooltip: {
          formatter: (p) =>
            `${p.data[3]}<br/>身高 ${p.data[0]} m · 体重 ${p.data[1]} kg<br/>种族值 ${p.data[2]}`,
        },
        legend: { type: 'scroll', bottom: 0, itemWidth: 10, itemHeight: 10 },
        grid: { left: 60, right: 30, top: 30, bottom: 70 },
        xAxis: { type: 'value', name: '身高 (m)', nameLocation: 'middle', nameGap: 28 },
        yAxis: { type: 'value', name: '体重 (kg)' },
        series: groups.map((g) => ({
          type: 'scatter',
          name: typeZh(g.type),
          data: g.data,
          symbolSize: (d) => Math.max(6, Math.sqrt(d[2]) / 2.4),
          itemStyle: { color: typeColor(g.type), opacity: 0.75 },
        })),
      }}
    />
  )
}
