import EChart from './EChart'

/** 排行横条 */
export default function StatsRankingChart({ items = [], metricLabel = '', loading }) {
  const data = [...items].reverse()
  return (
    <EChart
      loading={loading}
      height={Math.max(360, items.length * 22)}
      option={{
        tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>${metricLabel}：${p[0].value}` },
        grid: { left: 110, right: 40, top: 20, bottom: 40 },
        xAxis: { type: 'value', name: metricLabel },
        yAxis: {
          type: 'category',
          data: data.map((d) => d.name_zh || d.name),
          axisLabel: { fontSize: 12 },
        },
        series: [
          {
            type: 'bar',
            data: data.map((d) => ({
              value: d.value,
              itemStyle: { borderRadius: [0, 4, 4, 0] },
            })),
            barMaxWidth: 18,
            itemStyle: { color: '#1677ff' },
          },
        ],
      }}
    />
  )
}
