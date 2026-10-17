import { useEffect, useState } from 'react'
import {
  Drawer,
  Descriptions,
  Space,
  Progress,
  Typography,
  Empty,
  Spin,
  Tooltip,
  Tag,
  Button,
  Modal,
  App as AntApp,
} from 'antd'
import { BarChartOutlined, StarFilled, StarOutlined, FullscreenOutlined } from '@ant-design/icons'
import TypeTag from '@/components/common/TypeTag'
import PokemonAvatar from '@/components/common/PokemonAvatar'
import EvolutionChain from '@/components/pokemon/EvolutionChain'
import { useCompareStore, COMPARE_MAX } from '@/store/compareStore'
import { useFavoriteStore } from '@/store/favoriteStore'
import { getEvolution, listAbilities, listMoves } from '@/api/pokemon'
import {
  STAT_LABEL,
  STAT_ORDER,
  normalizeStats,
  toKg,
  toMeters,
  typeColor,
  damageClassZh,
} from '@/utils/constants'

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

// 招式默认折叠展示数量，避免一次渲染上百个标签
const MOVE_PREVIEW = 24

/** 招式悬停卡：威力/命中/PP/优先级（数据来自 move_detail 批量接口） */
function moveTooltip(m, detail) {
  if (!detail) return m.name
  const prio = detail.priority == null ? '—' : detail.priority > 0 ? `+${detail.priority}` : `${detail.priority}`
  return (
    <div className="move-tip">
      <div className="move-tip-name">
        {m.name_zh || m.name}
        <span>{m.name}</span>
      </div>
      <div className="move-tip-grid">
        <span>威力</span>
        <b>{detail.power ? detail.power : '—'}</b>
        <span>命中</span>
        <b>{detail.accuracy == null ? '必中' : detail.accuracy}</b>
        <span>PP</span>
        <b>{detail.pp ?? '—'}</b>
        <span>优先级</span>
        <b>{prio}</b>
        <span>类别</span>
        <b>{damageClassZh(detail.damage_class)}</b>
      </div>
    </div>
  )
}

/** 特性悬停卡：效果长文已机翻（P4），中文优先、无译文回落英文并如实标注 */
function abilityTooltip(a, detail) {
  return (
    <div className="move-tip">
      <div className="move-tip-name">
        {a.name_zh || a.name}
        <span>{a.name}</span>
      </div>
      {detail?.effect_zh || detail?.effect_en ? (
        <div className="move-tip-effect">
          <em>效果{detail?.effect_zh ? '' : '（英文）'}</em>
          {detail.effect_zh || detail.effect_en}
        </div>
      ) : (
        <div className="move-tip-effect">暂无效果数据</div>
      )}
      {detail?.holder_count != null && (
        <div className="move-tip-count">{detail.holder_count} 只宝可梦拥有该特性</div>
      )}
    </div>
  )
}

export default function PokemonDrawer({ pokemon, loading, open, onClose, onNavigate }) {
  const { message } = AntApp.useApp()
  const stats = normalizeStats(pokemon?.stats)
  const moves = pokemon?.moves || []
  const [expanded, setExpanded] = useState(false)
  const compareToggle = useCompareStore((s) => s.toggle)
  const compareIds = useCompareStore((s) => s.ids)
  const favToggle = useFavoriteStore((s) => s.toggle)
  const favIds = useFavoriteStore((s) => s.ids)

  // 进化链：按物种 slug 拉整棵树（从家族任意成员进入都能看到完整链）
  const [evolution, setEvolution] = useState(null)
  const [evoLoading, setEvoLoading] = useState(false)
  const [evoModal, setEvoModal] = useState(false)
  const speciesSlug = pokemon?.species_name || pokemon?.name
  useEffect(() => {
    if (!open || !speciesSlug) return
    let alive = true
    setEvoLoading(true)
    getEvolution(speciesSlug)
      .then((d) => alive && setEvolution(d))
      .catch(() => alive && setEvolution(null))
      .finally(() => alive && setEvoLoading(false))
    return () => {
      alive = false
    }
  }, [open, speciesSlug])

  // 招式/特性明细：各一次批量请求填满悬停卡，避免每个标签一次请求
  const [moveDetails, setMoveDetails] = useState({})
  const [abilityDetails, setAbilityDetails] = useState({})
  useEffect(() => {
    if (!open || !pokemon) return
    let alive = true
    const moveNames = (pokemon.moves || []).map((m) => m.name).filter(Boolean)
    const abilityNames = (pokemon.abilities || []).map((a) => a.name).filter(Boolean)
    if (moveNames.length) {
      listMoves({ names: moveNames.join(',') })
        .then((d) => {
          if (!alive) return
          const map = {}
          ;(d.items || []).forEach((m) => {
            map[m.name] = m
          })
          setMoveDetails(map)
        })
        .catch(() => alive && setMoveDetails({}))
    } else {
      setMoveDetails({})
    }
    if (abilityNames.length) {
      listAbilities({ names: abilityNames.join(',') })
        .then((d) => {
          if (!alive) return
          const map = {}
          ;(d.items || []).forEach((a) => {
            map[a.name] = a
          })
          setAbilityDetails(map)
        })
        .catch(() => alive && setAbilityDetails({}))
    } else {
      setAbilityDetails({})
    }
    return () => {
      alive = false
    }
  }, [open, pokemon])

  const inCompare = pokemon ? compareIds.includes(pokemon.id) : false
  const inFav = pokemon ? favIds.includes(pokemon.id) : false
  return (
    <Drawer
      size={480}
      open={open}
      onClose={onClose}
      title={pokemon ? pokemon.name_zh || pokemon.name : '详情'}
    >
      {loading ? (
        <Spin style={{ display: 'block', margin: '40px auto' }} />
      ) : !pokemon ? (
        <Empty description="暂无数据" />
      ) : (
        <>
          <div className="dex-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <PokemonAvatar
                src={pokemon.image_url}
                name={pokemon.name_zh || pokemon.name}
                alt={pokemon.name}
                type={pokemon.type_primary}
                size={88}
                ring
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span className="dex-id-chip">No. {String(pokemon.id).padStart(4, '0')}</span>
                <div className="dex-name-zh">{pokemon.name_zh || pokemon.name}</div>
                <div className="dex-name-en">{pokemon.name}</div>
              </div>
            </div>
            <div className="drawer-type-strip">
              {(pokemon.types || []).map((t) => (
                <div key={t} className="seg" style={{ background: typeColor(t) }} />
              ))}
            </div>
            <div>
              {(pokemon.types || []).map((t) => (
                <TypeTag key={t} name={t} />
              ))}
            </div>
            <div className="dex-actions">
              <Button
                size="small"
                type={inCompare ? 'primary' : 'default'}
                icon={<BarChartOutlined />}
                onClick={() => {
                  if (!inCompare && compareIds.length >= COMPARE_MAX) {
                    message.warning(`最多同时对比 ${COMPARE_MAX} 只，请先移除一只`)
                    return
                  }
                  compareToggle(pokemon.id)
                  message.success(inCompare ? '已移出对比' : '已加入对比')
                }}
              >
                {inCompare ? '已在对比栏' : '加入对比'}
              </Button>
              <Button
                size="small"
                icon={inFav ? <StarFilled style={{ color: '#f7b733' }} /> : <StarOutlined />}
                onClick={() => {
                  favToggle(pokemon.id)
                  message.success(inFav ? '已收藏' : '已收藏')
                }}
              >
                {inFav ? '已收藏' : '收藏'}
              </Button>
            </div>
          </div>

          {/* 固定标签列宽度：招式中文标签云内容很长，否则会把标签列挤成竖排文字 */}
          <Descriptions bordered size="small" column={2} labelStyle={{ width: 76, whiteSpace: 'nowrap' }}>
            <Descriptions.Item label="身高">{toMeters(pokemon.height).toFixed(1)} m</Descriptions.Item>
            <Descriptions.Item label="体重">{toKg(pokemon.weight).toFixed(1)} kg</Descriptions.Item>
            <Descriptions.Item label="种族值总和">{pokemon.stat_total}</Descriptions.Item>
            <Descriptions.Item label="基础经验">{pokemon.base_experience ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="招式数" span={2}>
              {pokemon.moves_count ?? '—'}
            </Descriptions.Item>
            <Descriptions.Item label="特性" span={2}>
              <Space size={4} wrap>
                {(pokemon.abilities || []).map((a) => (
                  <Tooltip key={a.name} title={abilityTooltip(a, abilityDetails[a.name])}>
                    <span className="stat-badge" style={{ background: a.is_hidden ? 'linear-gradient(135deg,#7952e8,#a78bfa)' : 'linear-gradient(135deg,#e3350d,#ff8a65)' }}>
                      {a.name_zh || a.name}
                      {a.is_hidden ? <span style={{ fontSize: 9, marginLeft: 4, opacity: 0.85 }}>隐藏</span> : null}
                    </span>
                  </Tooltip>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="招式" span={2}>
              {moves.length ? (
                <Space size={[4, 4]} wrap>
                  {(expanded ? moves : moves.slice(0, MOVE_PREVIEW)).map((m) => (
                    <Tooltip key={m.name} title={moveTooltip(m, moveDetails[m.name])}>
                      <Tag className="move-tag">{m.name_zh || m.name}</Tag>
                    </Tooltip>
                  ))}
                  {moves.length > MOVE_PREVIEW && (
                    <Button type="link" size="small" onClick={() => setExpanded((v) => !v)}>
                      {expanded ? '收起' : `展开全部 (${moves.length})`}
                    </Button>
                  )}
                </Space>
              ) : (
                '—'
              )}
            </Descriptions.Item>
          </Descriptions>

          <div className="evo-section-head">
            <Typography.Title level={5} style={{ margin: 0 }}>
              进化链
            </Typography.Title>
            <Button
              size="small"
              type="link"
              icon={<FullscreenOutlined />}
              onClick={() => setEvoModal(true)}
            >
              查看大图
            </Button>
          </div>
          <div className="evo-drawer-body">
            <EvolutionChain
              data={evolution}
              current={speciesSlug}
              loading={evoLoading}
              onPick={onNavigate}
            />
          </div>

          <Typography.Title level={5} style={{ marginTop: 20 }}>
            六维种族值
          </Typography.Title>
          <Space orientation="vertical" style={{ width: '100%' }} size={10}>
            {STAT_ORDER.map((k) => (
              <div key={k} className="stat-row">
                <span className="stat-row-label">{STAT_LABEL[k]}</span>
                <div className="stat-row-bar">
                  <Progress
                    percent={Math.min(100, Math.round((stats[k] / 180) * 100))}
                    showInfo={false}
                    size="small"
                    strokeColor={STAT_COLORS[k]}
                  />
                </div>
                <span className="stat-row-value" style={{ color: STAT_COLORS[k] }}>{stats[k]}</span>
              </div>
            ))}
          </Space>
        </>
      )}

      <Modal
        open={evoModal}
        onCancel={() => setEvoModal(false)}
        footer={null}
        width={760}
        title={
          evolution
            ? `${evolution.name_zh || evolution.species} 的进化链（${evolution.total_nodes} 个形态）`
            : '进化链'
        }
        destroyOnClose
      >
        <EvolutionChain
          data={evolution}
          current={speciesSlug}
          onNavigate={(node) => {
            setEvoModal(false)
            onNavigate?.(node)
          }}
          variant="h"
        />
      </Modal>
    </Drawer>
  )
}
