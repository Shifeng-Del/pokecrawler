import { useEffect, useRef, useState } from 'react'
import { Card, Input, Select, Slider, Button, Space, Row, Col, Switch, Divider } from 'antd'
import { SearchOutlined, ReloadOutlined, StarOutlined } from '@ant-design/icons'
import { TYPE_OPTIONS } from '@/utils/constants'
import { useDebounce } from '@/hooks/useDebounce'

export default function FilterBar({
  filters,
  onChange,
  onReset,
  abilities = [],
  speciesOptions = null,
  loading,
}) {
  const [keyword, setKeyword] = useState(filters.q || '')
  const debounced = useDebounce(keyword, 350)
  // 记录最近一次由本组件发出的 q，用于区分「用户输入」与「外部恢复（URL/重置）」
  const lastEmitted = useRef(filters.q || '')

  useEffect(() => {
    if (debounced !== (filters.q || '')) {
      lastEmitted.current = debounced
      onChange({ q: debounced })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced])

  // 外部来源的 q 变化（URL 恢复 / 重置按钮）→ 同步回输入框
  useEffect(() => {
    if ((filters.q || '') !== lastEmitted.current) {
      lastEmitted.current = filters.q || ''
      setKeyword(filters.q || '')
    }
  }, [filters.q])

  // value 必须保持英文 slug：后端按 slug 过滤；label 才是给用户看的中文
  const abilityOptions = abilities.map((a) => ({
    value: a.name,
    label: a.name_zh ? `${a.name_zh} · ${a.name} (${a.count})` : `${a.name} (${a.count})`,
  }))

  return (
    <Card className="filter-card" size="small" style={{ marginBottom: 16 }}>
      <Row gutter={[12, 12]} align="middle">
        <Col xs={24} sm={12} md={6}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索中文名或英文名，如 喷火龙 / char"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Select
            mode="multiple"
            allowClear
            style={{ width: '100%' }}
            placeholder="属性（同时满足）"
            value={filters.types}
            options={TYPE_OPTIONS}
            onChange={(v) => onChange({ types: v })}
            maxTagCount="responsive"
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Select
            showSearch
            allowClear
            style={{ width: '100%' }}
            placeholder="特性（支持中文）"
            value={filters.ability}
            options={abilityOptions}
            onChange={(v) => onChange({ ability: v })}
            filterOption={(input, option) => {
              // 同时匹配 label（中文）与 value（英文），否则中文化后英文反而搜不到
              const kw = input.toLowerCase()
              return (
                (option?.value || '').toLowerCase().includes(kw) ||
                (option?.label || '').toLowerCase().includes(kw)
              )
            }}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Space.Compact style={{ width: '100%' }}>
            <Select
              value={filters.sort}
              style={{ width: '58%' }}
              options={[
                { value: 'id', label: '编号' },
                { value: 'name', label: '名称' },
                { value: 'stat_total', label: '种族值' },
                { value: 'height', label: '身高' },
                { value: 'weight', label: '体重' },
                { value: 'base_experience', label: '经验值' },
              ]}
              onChange={(v) => onChange({ sort: v })}
            />
            <Select
              value={filters.order}
              style={{ width: '42%' }}
              options={[
                { value: 'asc', label: '升序' },
                { value: 'desc', label: '降序' },
              ]}
              onChange={(v) => onChange({ order: v })}
            />
          </Space.Compact>
        </Col>
        <Col xs={24} md={10}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, color: '#595959', whiteSpace: 'nowrap' }}>
              种族值区间
            </span>
            <Slider
              range
              style={{ flex: 1 }}
              min={0}
              max={800}
              step={10}
              value={[filters.minTotal ?? 0, filters.maxTotal ?? 800]}
              onChange={(v) => onChange({ minTotal: v[0], maxTotal: v[1] })}
              disabled={loading}
            />
          </div>
        </Col>
        <Col xs={24} md={4} style={{ textAlign: 'right' }}>
          <Space size={12}>
            <Space size={6}>
              <StarOutlined style={{ color: filters.favOnly ? '#f7b733' : '#9aa3b6' }} />
              <Switch
                size="small"
                checked={!!filters.favOnly}
                onChange={(v) => onChange({ favOnly: v })}
              />
              <span style={{ fontSize: 13, color: '#595959', whiteSpace: 'nowrap' }}>只看收藏</span>
            </Space>
            <Button icon={<ReloadOutlined />} onClick={onReset}>
              重置
            </Button>
          </Space>
        </Col>
      </Row>

      {/* P2 物种档案分类：数据就绪前整行隐藏，避免出现一堆空下拉 */}
      {speciesOptions && (
        <>
          <Divider style={{ margin: '4px 0 12px' }} orientation="left" orientationMargin={0}>
            <span style={{ fontSize: 12, color: '#8a93a8' }}>物种分类（图鉴档案）</span>
          </Divider>
          <Row gutter={[12, 12]} align="middle">
            <Col xs={24} sm={12} md={8}>
              <Select
                showSearch
                allowClear
                style={{ width: '100%' }}
                placeholder="物种分类（如 种子宝可梦）"
                value={filters.genus}
                options={speciesOptions.genus.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.count})`,
                }))}
                optionFilterProp="label"
                filterOption={(input, option) =>
                  (option?.label || '').toLowerCase().includes(input.toLowerCase())
                }
                onChange={(v) => onChange({ genus: v })}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Select
                allowClear
                style={{ width: '100%' }}
                placeholder="蛋组"
                value={filters.eggGroup}
                options={speciesOptions.egg_groups.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.count})`,
                }))}
                onChange={(v) => onChange({ eggGroup: v })}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Select
                allowClear
                style={{ width: '100%' }}
                placeholder="栖息地"
                value={filters.habitat}
                options={speciesOptions.habitats.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.count})`,
                }))}
                onChange={(v) => onChange({ habitat: v })}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Select
                allowClear
                style={{ width: '100%' }}
                placeholder="体色"
                value={filters.color}
                options={speciesOptions.colors.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.count})`,
                }))}
                onChange={(v) => onChange({ color: v })}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Select
                allowClear
                style={{ width: '100%' }}
                placeholder="体型"
                value={filters.shape}
                options={speciesOptions.shapes.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.count})`,
                }))}
                onChange={(v) => onChange({ shape: v })}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Select
                allowClear
                style={{ width: '100%' }}
                placeholder="成长率"
                value={filters.growthRate}
                options={speciesOptions.growth_rates.map((o) => ({
                  value: o.value,
                  label: `${o.label} (${o.count})`,
                }))}
                onChange={(v) => onChange({ growthRate: v })}
              />
            </Col>
          </Row>
        </>
      )}
    </Card>
  )
}
