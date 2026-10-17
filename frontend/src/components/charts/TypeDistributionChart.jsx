import { typeColor, typeZh } from '@/utils/constants'
import EChart from './EChart'

/** 属性分布：环形图 / 柱状图 */
export default function TypeDistributionChart({ items = [], mode = 'pie', onSelect, loading }) {
  const data = items.map((d) => ({
    name: typeZh(d.type),
    value: d.count,
    raw: d.type,
    itemStyle: { color: typeColor(d.type) },
  }))

  const option =
    mode === 'pie'
      ? {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 只 ({d}%)' },
          legend: { type: 'scroll', bottom: 0, itemWidth: 10, itemHeight: 10 },
          series: [
            {
              type: 'pie',
              radius: ['42%', '68%'],
              center: ['50%', '46%'],
              avoidLabelOverlap: true,
              itemStyle: { borderColor: '#fff', borderWidth: 2 },
              label: { formatter: '{b}\n{c}' },
              data,
            },
          ],
        }
      : {
          tooltip: { trigger: 'axis' },
          grid: { left: 50, right: 20, top: 30, bottom: 60 },
          xAxis: {
            type: 'category',
            data: data.map((d) => d.name),
            axisLabel: { rotate: 40, interval: 0 },
          },
          yAxis: { type: 'value', name: '数量' },
          series: [{ type: 'bar', data, barMaxWidth: 32 }],
        }

  return (
    <EChart
      option={option}
      height={360}
      loading={loading}
      onEvents={onSelect ? { click: (p) => onSelect(p.data?.raw) } : undefined}
    />
  )
}
