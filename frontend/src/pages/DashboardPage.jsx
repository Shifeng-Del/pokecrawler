import { Card, Col, Row, Statistic, Empty, Skeleton, Alert, Space } from 'antd'
import { DatabaseOutlined, ThunderboltOutlined, AppstoreOutlined, TrophyOutlined, ColumnHeightOutlined, DashboardOutlined, FieldTimeOutlined } from '@ant-design/icons'
import { useOverview, useTypeDistribution, useRanking } from '@/hooks/usePokemonStats'
import TypeDistributionChart from '@/components/charts/TypeDistributionChart'
import StatsRankingChart from '@/components/charts/StatsRankingChart'
import { useNavigate } from 'react-router-dom'
import { useFilterStore } from '@/store/filterStore'

export default function DashboardPage() {
  const navigate = useNavigate()
  const setFilters = useFilterStore((s) => s.setFilters)
  const { data: overview, isLoading } = useOverview()
  const { data: dist, isLoading: distLoading } = useTypeDistribution()
  const { data: ranking, isLoading: rankLoading } = useRanking('stat_total', 10)

  if (isLoading) return <Skeleton active paragraphs={6} />

  if (!overview?.total) {
    return (
      <Alert
        type="info"
        showIcon
        message="尚未采集数据"
        description={
          <Space orientation="vertical">
            <span>数据库为空，请先到「爬取管理」页面触发一次抓取。</span>
          </Space>
        }
        action={
          <a onClick={() => navigate('/crawl')}>前往爬取</a>
        }
      />
    )
  }

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <div className="page-banner">
        <div className="crumbs">
          <span>POKÉDEX</span>
          <span className="crumbs-sep">/</span>
          <span className="crumbs-cur">OVERVIEW</span>
        </div>
        <h3 className="page-banner-title">
          数据<span className="grad-text">总览</span>
        </h3>
        <p className="page-banner-sub">POKÉMON DEX OVERVIEW · 采集概况与核心指标全景</p>
        <div className="page-banner-badges">
          <span className="pk-badge">收录 <b>{overview.total}</b> 种</span>
          <span className="pk-badge">属性 <b>{overview.type_count}</b> 类</span>
          <span className="pk-badge">平均种族值 <b>{overview.avg_stat_total}</b></span>
        </div>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card className="stat-card tone-red">
            <span className="corner-glow" aria-hidden="true" />
            <span className="stat-index">01</span>
            <Statistic
              title="已收录宝可梦"
              value={overview.total}
              prefix={<DatabaseOutlined />}
            />
            <span className="stat-trend" aria-hidden="true">
              <i style={{ height: '40%' }} />
              <i style={{ height: '65%' }} />
              <i style={{ height: '50%' }} />
              <i style={{ height: '80%' }} />
              <i style={{ height: '95%' }} />
            </span>
            <span className="stat-foot">NATIONAL DEX</span>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="stat-card tone-blue">
            <span className="corner-glow" aria-hidden="true" />
            <span className="stat-index">02</span>
            <Statistic title="属性种类" value={overview.type_count} prefix={<AppstoreOutlined />} />
            <span className="stat-trend" aria-hidden="true">
              <i style={{ height: '70%' }} />
              <i style={{ height: '55%' }} />
              <i style={{ height: '85%' }} />
              <i style={{ height: '60%' }} />
              <i style={{ height: '90%' }} />
            </span>
            <span className="stat-foot">TYPE CATALOG</span>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="stat-card tone-gold">
            <span className="corner-glow" aria-hidden="true" />
            <span className="stat-index">03</span>
            <Statistic
              title="平均种族值"
              value={overview.avg_stat_total}
              prefix={<ThunderboltOutlined />}
            />
            <span className="stat-trend" aria-hidden="true">
              <i style={{ height: '50%' }} />
              <i style={{ height: '75%' }} />
              <i style={{ height: '60%' }} />
              <i style={{ height: '90%' }} />
              <i style={{ height: '70%' }} />
            </span>
            <span className="stat-foot">BASE STATS AVG</span>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="stat-card tone-violet">
            <span className="corner-glow" aria-hidden="true" />
            <span className="stat-index">04</span>
            <Statistic title="特性种类" value={overview.ability_count} prefix={<TrophyOutlined />} />
            <span className="stat-trend" aria-hidden="true">
              <i style={{ height: '60%' }} />
              <i style={{ height: '80%' }} />
              <i style={{ height: '45%' }} />
              <i style={{ height: '95%' }} />
              <i style={{ height: '65%' }} />
            </span>
            <span className="stat-foot">ABILITY COUNT</span>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card className="chart-card" title="属性分布">
            {dist?.items?.length ? (
              <TypeDistributionChart
                items={dist.items}
                loading={distLoading}
                onSelect={(type) => {
                  setFilters({ types: [type] })
                  navigate('/pokemon')
                }}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Card className="chart-card" title="种族值 TOP 10">
            {ranking?.items?.length ? (
              <StatsRankingChart
                items={ranking.items}
                metricLabel="种族值总和"
                loading={rankLoading}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <div className="mini-info">
            <ColumnHeightOutlined className="mini-icon" />
            <div className="mini-label">AVG HEIGHT</div>
            <div className="mini-value">
              {(overview.avg_height / 10).toFixed(2)}<span className="mini-unit">m</span>
            </div>
          </div>
        </Col>
        <Col xs={24} md={8}>
          <div className="mini-info">
            <DashboardOutlined className="mini-icon" />
            <div className="mini-label">AVG WEIGHT</div>
            <div className="mini-value">
              {(overview.avg_weight / 10).toFixed(2)}<span className="mini-unit">kg</span>
            </div>
          </div>
        </Col>
        <Col xs={24} md={8}>
          <div className="mini-info">
            <FieldTimeOutlined className="mini-icon" />
            <div className="mini-label">LAST CRAWL</div>
            <div className="mini-value" style={{ fontSize: 14, paddingTop: 4 }}>
              {overview.last_crawl_at?.slice(0, 19).replace('T', ' ') || '—'}
            </div>
          </div>
        </Col>
      </Row>
    </Space>
  )
}
