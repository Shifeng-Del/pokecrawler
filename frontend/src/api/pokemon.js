import client from './client'

/** 把筛选参数序列化为后端查询串 */
export function buildQuery(filters = {}) {
  const params = new URLSearchParams()
  const {
    q,
    types = [],
    typeAny = [],
    ability,
    minTotal,
    maxTotal,
    minHeight,
    maxHeight,
    minWeight,
    maxWeight,
    genus,
    eggGroup,
    habitat,
    color,
    shape,
    growthRate,
    sort,
    order,
    page,
    page_size: pageSize,
    ids,
  } = filters

  if (q) params.set('q', q)
  types.forEach((t) => params.append('type', t))
  typeAny.forEach((t) => params.append('type_any', t))
  if (ability) params.set('ability', ability)
  if (minTotal != null) params.set('min_total', minTotal)
  if (maxTotal != null) params.set('max_total', maxTotal)
  if (minHeight != null) params.set('min_height', minHeight)
  if (maxHeight != null) params.set('max_height', maxHeight)
  if (minWeight != null) params.set('min_weight', minWeight)
  if (maxWeight != null) params.set('max_weight', maxWeight)
  if (genus) params.set('genus', genus)
  if (eggGroup) params.set('egg_group', eggGroup)
  if (habitat) params.set('habitat', habitat)
  if (color) params.set('color', color)
  if (shape) params.set('shape', shape)
  if (growthRate) params.set('growth_rate', growthRate)
  if (sort) params.set('sort', sort)
  if (order) params.set('order', order)
  if (page) params.set('page', page)
  if (pageSize) params.set('page_size', pageSize)
  if (ids?.length) params.set('ids', ids.join(','))
  return params.toString()
}

export async function listPokemon(filters) {
  const { data } = await client.get(`/pokemon?${buildQuery(filters)}`)
  return data
}

export async function getPokemon(idOrName) {
  const { data } = await client.get(`/pokemon/${idOrName}`)
  return data
}

export async function getMetaTypes() {
  const { data } = await client.get('/pokemon/meta/types')
  return data
}

export async function getMetaAbilities(limit = 300) {
  const { data } = await client.get(`/pokemon/meta/abilities?limit=${limit}`)
  return data
}

/** 全量轻量索引（约 1351 条），供全局搜索面板本地过滤 */
export async function getPokemonIndex() {
  const { data } = await client.get('/pokemon/index')
  return data
}

/** P2 物种档案分类筛选项（genus/蛋组/栖息地/体色/体型/成长率） */
export async function getFilterOptions() {
  const { data } = await client.get('/pokemon/filter-options')
  return data
}

/** 进化链：id / 形态名 / 物种 slug 均可，返回整棵进化树 */
export async function getEvolution(idOrName) {
  const { data } = await client.get(`/pokemon/${encodeURIComponent(idOrName)}/evolution`)
  return data
}

/* ---------------------------------------------------------------- 招式图鉴 */
export async function listMoves(params = {}) {
  const { data } = await client.get('/moves', { params })
  return data
}

export async function getMove(name) {
  const { data } = await client.get(`/moves/${encodeURIComponent(name)}`)
  return data
}

/* ---------------------------------------------------------------- 特性明细 */
export async function listAbilities(params = {}) {
  const { data } = await client.get('/abilities', { params })
  return data
}

export async function getAbility(name) {
  const { data } = await client.get(`/abilities/${encodeURIComponent(name)}`)
  return data
}
