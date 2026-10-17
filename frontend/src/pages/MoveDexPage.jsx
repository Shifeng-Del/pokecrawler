import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Card, Space, Table, Tag, Typography, Empty, Modal, Descriptions, Select, Input, App as AntApp } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import TypeTag from '@/components/common/TypeTag'
import { listMoves, getMove } from '@/api/pokemon'
import { useDebounce } from '@/hooks/useDebounce'
import {
  TYPE_OPTIONS,
  damageClassZh,
  damageClassColor,
  generationZh,
} from '@/utils/constants'

const CLASS_OPTIONS = [
  { value: 'physical', label: '物理' },
  { value: 'special', label: '特殊' },
  { value: 'status', label: '变化' },
]

const SORT_OPTIONS = [
  { value: 'power', label: '威力' },
  { value: 'accuracy', label: '命中' },
  { value: 'pp', label: 'PP' },
  { value: 'priority', label: '优先级' },
  { value: 'name', label: '名称' },
]

/** URL → 查询参数（白名单字段，默认值不写回 URL） */
function paramsFromUrl(params) {
  return {
    q: params.get('q') || '',
    type: params.get('type') || '',
    cls: params.get('class') || '',
    gen: params.get('gen') || '',
    sort: params.get('sort') || 'power',
    order: params.get('order') || 'desc',
    page: Number(params.get('page')) || 1,
  }
}

export default function MoveDexPage() {
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const init = useMemo(() => paramsFromUrl(new URLSearchParams(searchParams)), []) // eslint-disable-line react-hooks/exhaustive-deps
  const [q, setQ] = useState(init.q)
  const [type, setType] = useState(init.type)
  const [cls, setCls] = useState(init.cls)
  const [gen, setGen] = useState(init.gen)
  const [sort, setSort] = useState(init.sort)
  const [order, setOrder] = useState(init.order)
  const [page, setPage] = useState(init.page)
  const [pageSize, setPageSize] = useState(50)
  const [detail, setDetail] = useState(null)
  const debouncedQ = useDebounce(q, 350)

  // 筛选变化回到第一页
  useEffect(() => {
    setPage(1)
  }, [debouncedQ, type, cls, gen, sort, order])

  const query = {
    q: debouncedQ || undefined,
    type_name: type || undefined,
    damage_class: cls || undefined,
    generation: gen || undefined,
    sort,
    order,
    page,
    page_size: pageSize,
  }
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['moves', query],
    queryFn: () => listMoves(query),
    placeholderData: (prev) => prev,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (error) message.error(error.message)
  }, [error])

  // 状态 → URL（replace，刷新不丢、链接可分享）
  useEffect(() => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (type) params.set('type', type)
    if (cls) params.set('class', cls)
    if (gen) params.set('gen', gen)
    if (sort !== 'power') params.set('sort', sort)
    if (order !== 'desc') params.set('order', order)
    if (page !== 1) params.set('page', page)
    setSearchParams(params, { replace: true })
  }, [q, type, cls, gen, sort, order, page, setSearchParams])

  const columns = [
    {
      title: '招式',
      key: 'name',
      width: 170,
      fixed: 'left',
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.name_zh || row.name}</div>
          <div style={{ fontSize: 11, color: '#8a93a8' }}>{row.name}</div>
        </div>
      ),
    },
    {
      title: '属性',
      dataIndex: 'type_name',
      key: 'type',
      width: 92,
      render: (v) => <TypeTag name={v} />,
    },
    {
      title: '类别',
      dataIndex: 'damage_class',
      key: 'damage_class',
      width: 80,
      render: (v) => (
        <Tag color={damageClassColor(v)} style={{ marginInlineEnd: 0 }}>
          {damageClassZh(v)}
        </Tag>
      ),
    },
    {
      title: '威力',
      dataIndex: 'power',
      key: 'power',
      width: 72,
      align: 'right',
      // 变化招式威力为 0 或 null，展示层统一按「—」处理
      render: (v) => (v ? <span style={{ fontWeight: 600 }}>{v}</span> : <span style={{ color: '#b6c0d4' }}>—</span>),
    },
    {
      title: '命中',
      dataIndex: 'accuracy',
      key: 'accuracy',
      width: 76,
      align: 'right',
      render: (v) => (v == null ? <span style={{ color: '#4096ff' }}>必中</span> : v),
    },
    { title: 'PP', dataIndex: 'pp', key: 'pp', width: 64, align: 'right' },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      align: 'right',
      render: (v) =>
        v == null ? '—' : v > 0 ? <span style={{ color: '#389e0d' }}>+{v}</span> : v < 0 ? <span style={{ color: '#cf1322' }}>{v}</span> : v,
    },
  ]

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <div className="page-banner">
        <div className="crumbs">
          <span>POKÉDEX</span>
          <span className="crumbs-sep">/</span>
          <span className="crumbs-cur">MOVES</span>
        </div>
        <h3 className="page-banner-title">
          招式<span className="grad-text">图鉴</span>
        </h3>
        <p className="page-banner-sub">MOVE DEX · 威力 / 命中 / PP / 优先级全查阅，悬停查看效果</p>
        <div className="page-banner-badges">
          <span className="pk-badge">
            {data ? (
              <>
                收录 <b>{data.total}</b> 个招式
              </>
            ) : (
              '加载中…'
            )}
          </span>
          <span className="pk-badge">
            点击任意行查看<span style={{ color: '#ffd9a0' }}>效果说明</span>
          </span>
        </div>
      </div>

      <Card className="filter-card" size="small">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索中文名或英文名，如 撞击 / tackle"
            style={{ width: 260 }}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Select
            allowClear
            showSearch
            style={{ width: 130 }}
            placeholder="属性"
            value={type || undefined}
            options={TYPE_OPTIONS.map((t) => ({ value: t.value, label: t.label }))}
            onChange={setType}
          />
          <Select
            allowClear
            style={{ width: 120 }}
            placeholder="类别"
            value={cls || undefined}
            options={CLASS_OPTIONS}
            onChange={setCls}
          />
          <Select
            allowClear
            style={{ width: 140 }}
            placeholder="世代"
            value={gen || undefined}
            options={[
              { value: 'generation-i', label: '第一世代' },
              { value: 'generation-ii', label: '第二世代' },
              { value: 'generation-iii', label: '第三世代' },
              { value: 'generation-iv', label: '第四世代' },
              { value: 'generation-v', label: '第五世代' },
              { value: 'generation-vi', label: '第六世代' },
              { value: 'generation-vii', label: '第七世代' },
              { value: 'generation-viii', label: '第八世代' },
              { value: 'generation-ix', label: '第九世代' },
            ]}
            onChange={setGen}
          />
          <Select
            style={{ width: 220 }}
            value={sort}
            options={SORT_OPTIONS}
            onChange={setSort}
          />
          <Select
            style={{ width: 100 }}
            value={order}
            options={[
              { value: 'desc', label: '降序' },
              { value: 'asc', label: '升序' },
            ]}
            onChange={setOrder}
          />
        </div>
      </Card>

      <Card className="list-card" size="small" title={`招式列表${data ? `（共 ${data.total} 条）` : ''}`}>
        <Table
          rowKey="name"
          size="small"
          loading={isLoading || isFetching}
          dataSource={data?.items || []}
          columns={columns}
          scroll={{ x: 760 }}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100],
            showTotal: (t) => `共 ${t} 个招式`,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
          }}
          onRow={(row) => ({ onClick: () => setDetail(row), style: { cursor: 'pointer' } })}
        />
      </Card>

      <Modal
        open={!!detail}
        onCancel={() => setDetail(null)}
        footer={null}
        width={560}
        title={detail ? `${detail.name_zh || detail.name} · ${detail.name}` : '招式详情'}
      >
        {detail && (
          <MoveDetailBody name={detail.name} />
        )}
      </Modal>
    </Space>
  )
}

/** 详情弹层主体：行内数据先渲染，效果长文按 name 现拉详情 */
function MoveDetailBody({ name }) {
  const { data, isLoading } = useQuery({
    queryKey: ['move-detail', name],
    queryFn: () => getMove(name),
    staleTime: 300_000,
  })
  const [showEn, setShowEn] = useState(false)
  if (isLoading || !data) {
    return <Empty description="加载中…" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  return (
    <Space orientation="vertical" size={14} style={{ width: '100%' }}>
      <Descriptions bordered size="small" column={2}>
        <Descriptions.Item label="属性">
          <TypeTag name={data.type_name} />
        </Descriptions.Item>
        <Descriptions.Item label="类别">
          <Tag color={damageClassColor(data.damage_class)}>{damageClassZh(data.damage_class)}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="威力">{data.power ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="命中">{data.accuracy == null ? '必中' : data.accuracy}</Descriptions.Item>
        <Descriptions.Item label="PP">{data.pp ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="优先级">{data.priority ?? 0}</Descriptions.Item>
        <Descriptions.Item label="世代">{generationZh(data.generation)}</Descriptions.Item>
        <Descriptions.Item label="可学会宝可梦">{data.learner_count} 只</Descriptions.Item>
      </Descriptions>
      {(data.effect_zh || data.effect_en) && (
        <div>
          <Typography.Text strong>
            效果
            {data.effect_en && (
              <a
                onClick={() => setShowEn((s) => !s)}
                style={{ marginLeft: 8, fontSize: 12, fontWeight: 400 }}
              >
                {showEn ? '中文' : '英文原文'}
              </a>
            )}
            {!data.effect_zh && (
              <small style={{ fontWeight: 400, color: '#8a93a8', marginLeft: 6 }}>（暂无译文）</small>
            )}
          </Typography.Text>
          <Typography.Paragraph style={{ marginTop: 4, marginBottom: 0 }}>
            {showEn && data.effect_en ? data.effect_en : data.effect_zh || data.effect_en}
          </Typography.Paragraph>
        </div>
      )}
      {(data.flavor_zh || data.flavor_en) && (
        <div>
          <Typography.Text strong>
            描述
            {data.flavor_en && (
              <a
                onClick={() => setShowEn((s) => !s)}
                style={{ marginLeft: 8, fontSize: 12, fontWeight: 400 }}
              >
                {showEn ? '中文' : '英文原文'}
              </a>
            )}
            {!data.flavor_zh && (
              <small style={{ fontWeight: 400, color: '#8a93a8', marginLeft: 6 }}>（暂无译文）</small>
            )}
          </Typography.Text>
          <Typography.Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 13 }}>
            {showEn && data.flavor_en ? data.flavor_en : data.flavor_zh || data.flavor_en}
          </Typography.Paragraph>
        </div>
      )}
    </Space>
  )
}
