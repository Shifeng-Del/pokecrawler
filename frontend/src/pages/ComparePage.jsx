import { useQueries } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Col, Empty, Row, Space, Table, Tag, Typography } from 'antd'
import {
  ArrowLeftOutlined,
  BarChartOutlined,
  ClearOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { getPokemon } from '@/api/pokemon'
import { useCompareStore } from '@/store/compareStore'
import { useFavoriteStore } from '@/store/favoriteStore'
import TypeTag from '@/components/common/TypeTag'
import AbilityRadarChart from '@/components/charts/AbilityRadarChart'
import { STAT_LABEL, STAT_ORDER, normalizeStats, toKg, toMeters } from '@/utils/constants'

const STAT_COLORS = {
  hp: '#52c41a',
  attack: '#fa541c',
  defense: '#1677ff',
  special_attack: '#eb2f96',
  special_defense: '#722ed1',
  speed: '#13c2c2',
}

export default function ComparePage() {
  const navigate = useNavigate()
  const { ids, remove, clear } = useCompareStore()
  const favToggle = useFavoriteStore((s) => s.toggle)
  const favIds = useFavoriteStore((s) => s.ids)

  // 每只宝可梦一个查询，共享 TanStack 缓存；详情已在列表页打开过的一般直接命中
  const queries = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['pokemon', 'detail', id],
      queryFn: () => getPokemon(id),
      staleTime: 60_000,
    })),
  })
  const details = queries.map((q) => q.data).filter(Boolean)
  const loading = queries.some((q) => q.isLoading)

  const rows = details.map((p) => {
    const stats = normalizeStats(p.stats)
    return {
      key: p.id,
      id: p.id,
      pokemon: p,
      ...stats,
      stat_total: p.stat_total,
      height: toMeters(p.height).toFixed(1),
      weight: toKg(p.weight).toFixed(1),
      base_experience: p.base_experience ?? '—',
    }
  })

  const columns = [
    {
      title: '宝可梦',
      dataIndex: 'pokemon',
      width: 190,
      render: (p) => (
        <div className="name-cell">
          <Typography.Text strong style={{ fontSize: 14 }}>
            {p.name_zh || p.name}
          </Typography.Text>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>
            No.{String(p.id).padStart(4, '0')} · {p.name}
          </div>
          <div style={{ marginTop: 4 }}>
            {(p.types || []).map((t) => (
              <TypeTag key={t} name={t} />
            ))}
          </div>
        </div>
      ),
    },
    ...STAT_ORDER.map((k) => ({
      title: STAT_LABEL[k],
      dataIndex: k,
      width: 76,
      render: (v) => (
        <span
          className="stat-badge"
          style={{ background: `linear-gradient(135deg, ${STAT_COLORS[k]}, ${STAT_COLORS[k]}cc)` }}
        >
          {v}
        </span>
      ),
    })),
    { title: '总和', dataIndex: 'stat_total', width: 80,
      render: (v) => <b style={{ color: '#e3350d', fontVariantNumeric: 'tabular-nums' }}>{v}</b> },
    { title: '身高', dataIndex: 'height', width: 80 },
    { title: '体重', dataIndex: 'weight', width: 80 },
    { title: '经验', dataIndex: 'base_experience', width: 70 },
    {
      title: '操作',
      width: 110,
      render: (_, r) => (
        <Space size={4}>
          <Button
            size="small"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => remove(r.id)}
          />
          <Button
            size="small"
            type="text"
            icon={
              <span style={{ color: favIds.includes(r.id) ? '#f7b733' : undefined }}>★</span>
            }
            onClick={() => favToggle(r.id)}
          />
        </Space>
      ),
    },
  ]

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <div className="page-banner">
        <div className="crumbs">
          <span>TOOLS</span>
          <span className="crumbs-sep">/</span>
          <span className="crumbs-cur">COMPARE</span>
        </div>
        <h3 className="page-banner-title">
          宝可梦<span className="grad-text">对比</span>
        </h3>
        <p className="page-banner-sub">COMPARE ARENA · 最多 3 只并排，六维雷达 + 数值明细</p>
        <div className="page-banner-badges">
          <span className="pk-badge">
            已加入 <b>{ids.length}</b> / 3
          </span>
          <span className="pk-badge">
            在列表页点开详情，点<span style={{ color: '#ffd9a0' }}>「加入对比」</span>即可收录
          </span>
        </div>
      </div>

      {ids.length === 0 ? (
        <Card className="list-card">
          <Empty description="对比栏还是空的">
            <Button type="primary" icon={<ArrowLeftOutlined />} onClick={() => navigate('/pokemon')}>
              去列表页挑选宝可梦
            </Button>
          </Empty>
        </Card>
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card className="chart-card" title="六维雷达对比" loading={loading}>
                {details.length ? (
                  <AbilityRadarChart items={details} />
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="加载中…" />
                )}
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card
                className="chart-card"
                title="数值明细"
                loading={loading}
                extra={
                  <Button size="small" icon={<ClearOutlined />} onClick={clear}>
                    清空对比
                  </Button>
                }
              >
                <Table
                  size="small"
                  pagination={false}
                  dataSource={rows}
                  columns={columns}
                  scroll={{ x: 960 }}
                  style={{ marginTop: 4 }}
                />
                <div style={{ marginTop: 12, fontSize: 12, color: '#9aa3b6' }}>
                  <BarChartOutlined style={{ marginRight: 6 }}
                  />雷达图与列表实时联动：在抽屉里继续「加入对比」可随时扩充
                </div>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Space>
  )
}
