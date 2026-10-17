import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Space, App as AntApp, Button } from 'antd'
import PokemonTable from '@/components/pokemon/PokemonTable'
import PokemonDrawer from '@/components/pokemon/PokemonDrawer'
import FilterBar from '@/components/common/FilterBar'
import ExportButtons from '@/components/common/ExportButtons'
import { usePokemonList } from '@/hooks/usePokemonList'
import { getFilterOptions, getMetaAbilities, getPokemon } from '@/api/pokemon'
import { useFilterStore } from '@/store/filterStore'
import { useFavoriteStore } from '@/store/favoriteStore'

/** URL → filters（只认白名单字段，默认值不写回 URL） */
function filtersFromParams(params) {
  const num = (v) => (v == null || v === '' ? undefined : Number(v))
  return {
    q: params.get('q') || '',
    types: params.getAll('type'),
    typeAny: params.getAll('type_any'),
    ability: params.get('ability') || undefined,
    minTotal: num(params.get('min_total')),
    maxTotal: num(params.get('max_total')),
    genus: params.get('genus') || undefined,
    eggGroup: params.get('egg_group') || undefined,
    habitat: params.get('habitat') || undefined,
    color: params.get('color') || undefined,
    shape: params.get('shape') || undefined,
    growthRate: params.get('growth_rate') || undefined,
    sort: params.get('sort') || 'id',
    order: params.get('order') || 'asc',
    favOnly: params.get('fav') === '1',
    page: num(params.get('page')) || 1,
    pageSize: num(params.get('page_size')) || 20,
  }
}

export default function PokemonListPage() {
  const { message } = AntApp.useApp()
  const { filters, setFilters, resetFilters, pendingType, takePendingType, takePendingDetailId } =
    useFilterStore()
  const favIds = useFavoriteStore((s) => s.ids)
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [abilities, setAbilities] = useState([])
  const [speciesOptions, setSpeciesOptions] = useState(null)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 从图表页跳转过来时带上的属性筛选
  useEffect(() => {
    const type = takePendingType()
    if (type) setFilters({ types: [type] })
  }, [])

  useEffect(() => {
    if (pendingType) {
      setFilters({ types: [pendingType] })
      takePendingType()
    }
  }, [pendingType])

  useEffect(() => {
    getMetaAbilities()
      .then((d) => setAbilities(d.abilities || []))
      .catch(() => setAbilities([]))
    getFilterOptions()
      .then(setSpeciesOptions)
      .catch(() => setSpeciesOptions(null))
  }, [])

  // 挂载时从 URL 恢复筛选/分页状态（刷新不丢、链接可分享）
  const urlInit = useRef(false)
  useEffect(() => {
    if (urlInit.current) return
    urlInit.current = true
    const f = filtersFromParams(new URLSearchParams(searchParams))
    setPage(f.page)
    setPageSize(f.pageSize)
    setFilters({
      q: f.q,
      types: f.types,
      typeAny: f.typeAny,
      ability: f.ability,
      minTotal: f.minTotal,
      maxTotal: f.maxTotal,
      genus: f.genus,
      eggGroup: f.eggGroup,
      habitat: f.habitat,
      color: f.color,
      shape: f.shape,
      growthRate: f.growthRate,
      sort: f.sort,
      order: f.order,
      favOnly: f.favOnly,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 筛选变化时回到第一页（按序列化值比较而非引用，避免 setFilters 造成的
  // 无变化引用更新把翻页弹回第 1 页；URL 初始化触发的那次跳过）
  const firstFilters = useRef(true)
  const filterSig = useRef(null)
  useEffect(() => {
    const sig = JSON.stringify(filters)
    if (firstFilters.current) {
      firstFilters.current = false
      filterSig.current = sig
      return
    }
    if (sig === filterSig.current) return
    filterSig.current = sig
    setPage(1)
  }, [filters])

  // 收藏开关打开时把收藏 id 集合下推给后端；无收藏时用不可能命中的占位 id 换取空结果
  const query = {
    ...filters,
    page,
    page_size: pageSize,
    ...(filters.favOnly ? { ids: favIds.length ? favIds : ['-1'] } : {}),
  }
  const { data, isLoading, isFetching, error } = usePokemonList(query)

  useEffect(() => {
    if (error) message.error(error.message)
  }, [error])

  // 筛选/分页变化 → 写回 URL（replace，不堆历史记录）
  useEffect(() => {
    const params = new URLSearchParams()
    if (filters.q) params.set('q', filters.q)
    filters.types.forEach((t) => params.append('type', t))
    filters.typeAny.forEach((t) => params.append('type_any', t))
    if (filters.ability) params.set('ability', filters.ability)
    if (filters.minTotal != null) params.set('min_total', filters.minTotal)
    if (filters.maxTotal != null) params.set('max_total', filters.maxTotal)
    if (filters.genus) params.set('genus', filters.genus)
    if (filters.eggGroup) params.set('egg_group', filters.eggGroup)
    if (filters.habitat) params.set('habitat', filters.habitat)
    if (filters.color) params.set('color', filters.color)
    if (filters.shape) params.set('shape', filters.shape)
    if (filters.growthRate) params.set('growth_rate', filters.growthRate)
    if (filters.sort && filters.sort !== 'id') params.set('sort', filters.sort)
    if (filters.order && filters.order !== 'asc') params.set('order', filters.order)
    if (filters.favOnly) params.set('fav', '1')
    if (page !== 1) params.set('page', page)
    if (pageSize !== 20) params.set('page_size', pageSize)
    setSearchParams(params, { replace: true })
  }, [filters, page, pageSize, setSearchParams])

  const openDetail = async (row) => {
    setSelected(row)
    setDetailLoading(true)
    try {
      setDetail(await getPokemon(row.id))
    } catch (err) {
      message.error(err.message)
    } finally {
      setDetailLoading(false)
    }
  }

  // 全局搜索面板跳过来：自动打开对应宝可梦的抽屉
  useEffect(() => {
    const id = takePendingDetailId()
    if (id) openDetail({ id })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <div className="page-banner">
        <div className="crumbs">
          <span>POKÉDEX</span>
          <span className="crumbs-sep">/</span>
          <span className="crumbs-cur">LIST</span>
        </div>
        <h3 className="page-banner-title">
          宝可梦<span className="grad-text">数据列表</span>
        </h3>
        <p className="page-banner-sub">NATIONAL DEX · 全量收录，支持搜索、筛选与排序</p>
        <div className="page-banner-badges">
          <span className="pk-badge">
            {data ? (
              <>
                当前筛选 <b>{data.total}</b> 条
              </>
            ) : (
              '加载中…'
            )}
          </span>
          <span className="pk-badge">
            {filters.favOnly ? (
              <>
                收藏夹 <b>{favIds.length}</b> 只
              </>
            ) : (
              <>
                点击任意行查看<span style={{ color: '#ffd9a0' }}>图鉴详情</span>
              </>
            )}
          </span>
        </div>
      </div>
      <FilterBar
        filters={filters}
        abilities={abilities}
        speciesOptions={speciesOptions}
        loading={isFetching}
        onChange={(patch) => setFilters(patch)}
        onReset={() => {
          resetFilters()
          setPage(1)
        }}
      />

      <Card
        className="list-card"
        size="small"
        title={`数据列表${data ? `（共 ${data.total} 条）` : ''}`}
        extra={<ExportButtons filters={filters} />}
      >
        <PokemonTable
          data={data?.items || []}
          loading={isLoading || isFetching}
          page={page}
          pageSize={pageSize}
          total={data?.total || 0}
          onChange={({ page: p, pageSize: ps, sort, order }) => {
            setPage(p)
            setPageSize(ps)
            // 仅在排序真变化时写 filters：setFilters 必然改变 filters 引用，
            // 会触发「筛选变化回第一页」的副作用，把翻页弹回第 1 页
            if (filters.sort !== sort || filters.order !== order) {
              setFilters({ sort, order })
            }
          }}
          onRow={openDetail}
        />
      </Card>

      <PokemonDrawer
        pokemon={detail}
        loading={detailLoading}
        open={!!selected}
        onClose={() => setSelected(null)}
        onNavigate={(node) => node?.pokemon_id && openDetail({ id: node.pokemon_id })}
      />
    </Space>
  )
}
