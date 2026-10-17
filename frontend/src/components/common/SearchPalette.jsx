import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AutoComplete, Empty, Input, Spin, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { getPokemonIndex } from '@/api/pokemon'
import { useFilterStore } from '@/store/filterStore'
import { typeColor } from '@/utils/constants'

/** 本地过滤：编号精确优先，其次中文名/英文名包含匹配 */
function matchItems(items, kw) {
  const q = kw.trim().toLowerCase()
  if (!q) return []
  const starts = []
  const contains = []
  for (const it of items) {
    const zh = it.name_zh || ''
    const en = it.name || ''
    if (String(it.id) === q || en.toLowerCase() === q || zh === kw.trim()) {
      starts.push(it)
    } else if (
      en.toLowerCase().includes(q) ||
      zh.includes(kw.trim()) ||
      String(it.id).includes(q)
    ) {
      contains.push(it)
    }
    if (starts.length >= 8) break
  }
  return [...starts, ...contains].slice(0, 30)
}

export default function SearchPalette({ open, onClose }) {
  const navigate = useNavigate()
  const setPendingDetailId = useFilterStore((s) => s.setPendingDetailId)
  const [keyword, setKeyword] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['pokemon-index'],
    queryFn: getPokemonIndex,
    staleTime: 5 * 60 * 1000,
    enabled: open,
  })

  const options = useMemo(() => {
    const items = matchItems(data?.items || [], keyword)
    return items.map((it) => ({
      value: String(it.id),
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '3px 0' }}>
          <span style={{ color: '#9aa3b6', fontSize: 12, fontVariantNumeric: 'tabular-nums', minWidth: 34 }}>
            No.{String(it.id).padStart(4, '0')}
          </span>
          <Typography.Text strong style={{ fontSize: 14 }}>
            {it.name_zh || it.name}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {it.name}
          </Typography.Text>
          {it.type ? (
            <span className="type-tag" style={{ background: typeColor(it.type), marginLeft: 'auto' }}>
              {it.type}
            </span>
          ) : null}
        </div>
      ),
    }))
  }, [data, keyword])

  const openDetail = (id) => {
    onClose()
    setKeyword('')
    setPendingDetailId(Number(id))
    navigate('/pokemon')
  }

  return (
    <AutoComplete
      open={open}
      onOpenChange={(v) => !v && onClose()}
      value={keyword}
      onChange={setKeyword}
      options={options}
      onSelect={(val) => openDetail(val)}
      style={{ width: '100%' }}
      listHeight={380}
      notFoundContent={
        isLoading ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Spin size="small" />
          </div>
        ) : keyword.trim() ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的宝可梦" />
        ) : (
          <div style={{ textAlign: 'center', padding: '14px 0', color: '#9aa3b6', fontSize: 13 }}>
            输入编号 / 中文名 / 英文名开始搜索
          </div>
        )
      }
    >
      <Input
        autoFocus
        size="large"
        allowClear
        prefix={<SearchOutlined style={{ color: '#e3350d' }} />}
        placeholder="搜索宝可梦：喷火龙 / charizard / 6…"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose()
        }}
      />
    </AutoComplete>
  )
}
