import { useState } from 'react'
import { Card, Col, Row, Segmented, Select, Space, Empty, Input, Button } from 'antd'
import {
  useTypeDistribution,
  useTypeMatrix,
  useHeightWeight,
  useRanking,
  useRadar,
} from '@/hooks/usePokemonStats'
import TypeDistributionChart from '@/components/charts/TypeDistributionChart'
import TypeMatrixHeatmap from '@/components/charts/TypeMatrixHeatmap'
import AbilityRadarChart from '@/components/charts/AbilityRadarChart'
import HeightWeightScatter from '@/components/charts/HeightWeightScatter'
import StatsRankingChart from '@/components/charts/StatsRankingChart'
import TypeStatsBarChart from '@/components/charts/TypeStatsBarChart'
import { METRIC_OPTIONS } from '@/utils/constants'
import { useNavigate } from 'react-router-dom'
import { useFilterStore } from '@/store/filterStore'

export default function ChartsPage() {
  const navigate = useNavigate()
  const setPendingType = useFilterStore((s) => s.setPendingType)

  const [pieMode, setPieMode] = useState('pie')
  const [metric, setMetric] = useState('stat_total')
  const [radarIds, setRadarIds] = useState('1,4,7')

  const dist = useTypeDistribution('count')
  const matrix = useTypeMatrix()
  const hw = useHeightWeight('scatter')
  const ranking = useRanking(metric, 20)
  const radar = useRadar(radarIds.split(',').map((s) => Number(s.trim())).filter(Boolean))

  const jumpToList = (type) => {
    setPendingType(type)
    navigate('/pokemon')
  }

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <div className="page-banner">
        <div className="crumbs">
          <span>POKÉDEX</span>
          <span className="crumbs-sep">/</span>
          <span className="crumbs-cur">ANALYTICS</span>
        </div>
        <h3 className="page-banner-title">
          图表<span className="grad-text">分析</span>
        </h3>
        <p className="page-banner-sub">ANALYTICS · 属性分布 · 六维对比 · 体型关系 · 综合排行</p>
        <div className="page-banner-badges">
          <span className="pk-badge">18 属性 · <b>18×18</b> 组合矩阵</span>
          <span className="pk-badge">支持点击图表联动跳转</span>
        </div>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            className="chart-card"
            title="属性分布"
            extra={
              <Segmented
                value={pieMode}
                onChange={setPieMode}
                options={[
                  { label: '环形', value: 'pie' },
                  { label: '柱状', value: 'bar' },
                ]}
              />
            }
          >
            {dist.data?.items?.length ? (
              <TypeDistributionChart
                items={dist.data.items}
                mode={pieMode}
                loading={dist.isLoading}
                onSelect={jumpToList}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card className="chart-card" title="双属性组合热力图">
            {matrix.data?.items?.length ? (
              <TypeMatrixHeatmap items={matrix.data.items} loading={matrix.isLoading} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card className="chart-card" title="各属性六维均值">
            {dist.data?.items?.length ? (
              <TypeStatsBarChart items={dist.data.items} loading={dist.isLoading} />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            className="chart-card"
            title="能力雷达对比"
            extra={
              <Space>
                <Input
                  size="small"
                  style={{ width: 140 }}
                  value={radarIds}
                  placeholder="id，如 1,4,7"
                  onChange={(e) => setRadarIds(e.target.value)}
                />
              </Space>
            }
          >
            {radar.data?.items?.length ? (
              <AbilityRadarChart items={radar.data.items} loading={radar.isLoading} />
            ) : (
              <Empty description="暂无数据，请输入有效 id" />
            )}
          </Card>
        </Col>
      </Row>

      <Card className="chart-card" title="身高 × 体重分布（气泡大小=种族值）">
        {hw.data?.items?.length ? (
          <HeightWeightScatter items={hw.data.items} loading={hw.isLoading} />
        ) : (
          <Empty description="暂无数据" />
        )}
      </Card>

      <Card
        className="chart-card"
        title="排行榜"
        extra={
          <Space>
            <Select
              value={metric}
              style={{ width: 140 }}
              options={METRIC_OPTIONS}
              onChange={setMetric}
            />
            <Button onClick={() => navigate('/pokemon')}>查看完整列表</Button>
          </Space>
        }
      >
        {ranking.data?.items?.length ? (
          <StatsRankingChart
            items={ranking.data.items}
            metricLabel={ranking.data.metric_label}
            loading={ranking.isLoading}
          />
        ) : (
          <Empty description="暂无数据" />
        )}
      </Card>
    </Space>
  )
}
