import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { Badge, Button, Space, Typography } from 'antd'
import { BarChartOutlined, CloseOutlined } from '@ant-design/icons'
import { getPokemonIndex } from '@/api/pokemon'
import { useCompareStore } from '@/store/compareStore'

/** 悬浮对比栏：有暂存且不在对比页时显示 */
export default function CompareBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { ids, remove, clear } = useCompareStore()

  const { data } = useQuery({
    queryKey: ['pokemon-index'],
    queryFn: getPokemonIndex,
    staleTime: 5 * 60 * 1000,
    enabled: ids.length > 0,
  })
  const byId = new Map((data?.items || []).map((it) => [it.id, it]))

  if (ids.length === 0 || location.pathname === '/compare') return null

  return (
    <div className="compare-bar">
      <Space size={10} wrap style={{ minWidth: 0 }}>
        <Typography.Text strong style={{ fontSize: 13, color: '#45506a', whiteSpace: 'nowrap' }}>
          对比栏
        </Typography.Text>
        {ids.map((id) => {
          const it = byId.get(id)
          return (
            <span key={id} className="compare-chip">
              <span className="compare-chip-name">{it?.name_zh || it?.name || `No.${id}`}</span>
              <CloseOutlined className="compare-chip-x" onClick={() => remove(id)} />
            </span>
          )
        })}
      </Space>
      <Space size={8} style={{ flexShrink: 0 }}>
        <Button size="small" type="text" onClick={clear}>
          清空
        </Button>
        <Button
          size="small"
          type="primary"
          icon={<BarChartOutlined />}
          onClick={() => navigate('/compare')}
        >
          开始对比
          <Badge count={ids.length} size="small" color="#f7b733" style={{ marginLeft: 6 }} />
        </Button>
      </Space>
    </div>
  )
}
