import { Table, Space, Typography, Progress, Tooltip } from 'antd'
import TypeTag from '@/components/common/TypeTag'
import PokemonAvatar from '@/components/common/PokemonAvatar'
import { STAT_ORDER, STAT_LABEL, toKg, toMeters } from '@/utils/constants'

const STAT_COLORS = {
  hp: '#52c41a',
  attack: '#fa541c',
  defense: '#1677ff',
  special_attack: '#eb2f96',
  special_defense: '#722ed1',
  speed: '#13c2c2',
}

const STAT_KEY_SHORT = {
  hp: 'HP',
  attack: 'ATK',
  defense: 'DEF',
  special_attack: 'SpA',
  special_defense: 'SpD',
  speed: 'SPE',
}

export default function PokemonTable({ data = [], loading, page, pageSize, total, onChange, onRow }) {
  const columns = [
    {
      title: '#',
      dataIndex: 'id',
      width: 80,
      sorter: true,
      render: (id, row, index) => {
        // 连续行号：与「共 N 条」及翻页位置一致。
        // PokeAPI 给超级/超极巨等形态分配了 10000+ 的内部 id，直接展示会让
        // 用户误以为收录量过万（如第 68 页首行 10316 vs 总数 1351）。
        const rowNo = (page - 1) * pageSize + index + 1
        const idTip =
          id <= 1025
            ? `全国图鉴编号 No.${String(id).padStart(4, '0')}`
            : `特殊形态（上游内部编号 ${id}，非全国图鉴编号）`
        return (
          <Space size={8}>
            <PokemonAvatar
              src={row.image_url}
              name={row.name_zh || row.name}
              alt={row.name}
              type={row.type_primary}
              size={40}
            />
            <Tooltip title={idTip}>
              <span className="id-pill">{String(rowNo).padStart(4, '0')}</span>
            </Tooltip>
          </Space>
        )
      },
    },
    {
      title: '名称',
      dataIndex: 'name',
      sorter: true,
      render: (name, row) => (
        <div className="name-cell" style={{ lineHeight: 1.35 }}>
          <Typography.Text strong>{row.name_zh || name}</Typography.Text>
          <div style={{ fontSize: 12, color: '#8c95a8', fontStyle: 'italic' }}>{name}</div>
        </div>
      ),
    },
    {
      title: '属性',
      key: 'types',
      width: 150,
      render: (_, row) => (
        <span>
          {(row.types || []).map((t) => (
            <TypeTag key={t} name={t} />
          ))}
        </span>
      ),
    },
    {
      title: '种族值',
      dataIndex: 'stat_total',
      width: 120,
      sorter: true,
      render: (v) => (
        <div className="gradient-progress" style={{ minWidth: 80 }}>
          <Progress
            percent={Math.min(100, Math.round((v / 700) * 100))}
            size="small"
            format={() => <span style={{ fontWeight: 700, color: '#3c4a6b' }}>{v}</span>}
          />
        </div>
      ),
    },
    {
      title: '六维',
      key: 'stats',
      width: 200,
      render: (_, row) => {
        const stats = row.stats || {}
        return (
          <Space size={3} wrap>
            {STAT_ORDER.map((k) => {
              const key = k === 'special_attack' ? 'special-attack' : k
              const key2 = k === 'special_defense' ? 'special-defense' : key
              return (
                <Tooltip key={k} title={`${STAT_LABEL[k]} · ${STAT_KEY_SHORT[k]}`}>
                  <span className="stat-chip" style={{ background: STAT_COLORS[k] }}>
                    {stats[key2] ?? 0}
                  </span>
                </Tooltip>
              )
            })}
          </Space>
        )
      },
    },
    {
      title: '身高',
      dataIndex: 'height',
      width: 90,
      sorter: true,
      render: (v) => `${toMeters(v).toFixed(1)} m`,
    },
    {
      title: '体重',
      dataIndex: 'weight',
      width: 100,
      sorter: true,
      render: (v) => `${toKg(v).toFixed(1)} kg`,
    },
    {
      title: '基础经验',
      dataIndex: 'base_experience',
      width: 100,
      sorter: true,
    },
  ]

  return (
    <Table
      rowKey="id"
      loading={loading}
      columns={columns}
      dataSource={data}
      size="middle"
      onRow={(row) => ({ onClick: () => onRow?.(row), style: { cursor: 'pointer' } })}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        showTotal: (t) => `共 ${t} 条`,
        pageSizeOptions: [20, 50, 100],
      }}
      onChange={(p, _f, sorter) => {
        const field = Array.isArray(sorter) ? sorter[0]?.field : sorter?.field
        const order = Array.isArray(sorter) ? sorter[0]?.order : sorter?.order
        onChange?.({
          page: p.current,
          pageSize: p.pageSize,
          sort: field || 'id',
          order: order === 'descend' ? 'desc' : 'asc',
        })
      }}
      scroll={{ x: 1040 }}
    />
  )
}
