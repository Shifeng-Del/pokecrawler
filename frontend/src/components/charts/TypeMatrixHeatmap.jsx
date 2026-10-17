import { TYPE_INFO, typeZh } from '@/utils/constants'
import EChart from './EChart'

/** 主属性 × 副属性 组合热力图 */
export default function TypeMatrixHeatmap({ items = [], loading }) {
  const types = Object.keys(TYPE_INFO)
  const index = new Map(types.map((t, i) => [t, i]))
  const matrix = types.map(() => types.map(() => 0))
  let max = 0

  items.forEach((d) => {
    const i = index.get(d.primary)
    const j = index.get(d.secondary)
    if (i == null) return
    if (j == null) return
    matrix[i][j] += d.count
    max = Math.max(max, matrix[i][j])
  })

  const data = []
  matrix.forEach((row, i) => row.forEach((v, j) => data.push([j, i, v])))

  return (
    <EChart
      loading={loading}
      height={420}
      option={{
        tooltip: {
          formatter: (p) =>
            `${typeZh(types[p.value[1]])} × ${typeZh(types[p.value[0]])}：${p.value[2]} 只`,
        },
        grid: { left: 80, right: 20, top: 20, bottom: 90 },
        xAxis: {
          type: 'category',
          data: types.map(typeZh),
          splitArea: { show: true },
          axisLabel: { rotate: 45 },
        },
        yAxis: {
          type: 'category',
          data: types.map(typeZh),
          splitArea: { show: true },
        },
        visualMap: {
          min: 0,
          max: max || 1,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: 10,
          inRange: { color: ['#f6faff', '#c6e2ff', '#69b1ff', '#1677ff'] },
        },
        series: [
          {
            type: 'heatmap',
            data,
            emphasis: { itemStyle: { borderColor: '#333', borderWidth: 1 } },
          },
        ],
      }}
    />
  )
}
