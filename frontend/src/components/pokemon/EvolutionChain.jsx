import { Empty, Spin, Tooltip } from 'antd'
import PokemonAvatar from '@/components/common/PokemonAvatar'
import {
  EVOLUTION_TRIGGER_ZH,
  ITEM_ZH,
  LOCATION_ZH,
  NATURE_ZH,
  TIME_OF_DAY_ZH,
  typeZh,
  zhOf,
} from '@/utils/constants'

/** 把 detail_json 里的一个条件变体格式化为中文说明 */
function formatVariant(v) {
  if (!v || typeof v !== 'object') return ''
  const parts = []
  if (v.min_level) parts.push(`等级 ${v.min_level}`)
  if (v.item?.name) parts.push(zhOf(ITEM_ZH, v.item.name))
  if (v.held_item?.name) parts.push(`携带 ${zhOf(ITEM_ZH, v.held_item.name)}`)
  if (v.known_move?.name) parts.push(`学会 ${v.known_move.name_zh || v.known_move.name}`)
  if (v.known_move_type) parts.push(`${typeZh(v.known_move_type)}属性招式`)
  if (v.location?.name) parts.push(`地点 ${zhOf(LOCATION_ZH, v.location.name)}`)
  if (v.time_of_day) parts.push(zhOf(TIME_OF_DAY_ZH, v.time_of_day))
  if (v.gender != null) parts.push(v.gender === 1 ? '雌性' : v.gender === 2 ? '雄性' : '无性别')
  if (v.min_happiness) parts.push(`亲密度 ${v.min_happiness}`)
  if (v.min_affection) parts.push(`友好度 ${v.min_affection}`)
  if (v.min_beauty) parts.push(`美丽度 ${v.min_beauty}`)
  if (v.needs_overworld_rain) parts.push('需要下雨')
  if (v.turn_upside_down) parts.push('倒置主机')
  if (v.relative_physical_stats != null) {
    parts.push(
      v.relative_physical_stats === 1
        ? '攻击大于防御'
        : v.relative_physical_stats === -1
          ? '攻击小于防御'
          : `攻防关系 ${v.relative_physical_stats}`,
    )
  }
  if (v.min_move_count) parts.push(`将招式使用 ${v.min_move_count} 次`)
  if (v.min_steps) parts.push(`步行 ${v.min_steps} 步`)
  if (v.min_damage_taken) parts.push(`累计受到 ${v.min_damage_taken} 以上伤害`)
  if (v.needs_multiplayer) parts.push('需要联机游玩')
  if (v.allowed_natures?.length) {
    parts.push(`限定性格：${v.allowed_natures.map((n) => zhOf(NATURE_ZH, n.name)).join('、')}`)
  }
  return parts.join(' · ') || '无条件'
}

/** 单条进化边的摘要标签：Lv.16 / 火之石 / 通信交换 · 夜晚 */
function conditionLabel(cond) {
  if (!cond) return ''
  const parts = []
  if (cond.min_level) parts.push(`Lv.${cond.min_level}`)
  if (cond.item) parts.push(zhOf(ITEM_ZH, cond.item))
  if (cond.time_of_day) parts.push(zhOf(TIME_OF_DAY_ZH, cond.time_of_day))
  if (!parts.length) parts.push(cond.trigger_zh || zhOf(EVOLUTION_TRIGGER_ZH, cond.trigger))
  return parts.join(' · ')
}

function ConditionChips({ conditions }) {
  return (
    <div className="evo-conds">
      {conditions.map((c, i) => (
        <Tooltip
          key={`${c.trigger}-${i}`}
          title={
            <div className="evo-tip">
              <div className="evo-tip-title">{c.trigger_zh || c.trigger}</div>
              {(c.variants || []).map((v, j) => (
                <div key={j} className="evo-tip-line">
                  {formatVariant(v)}
                </div>
              ))}
              {!c.variants?.length && <div className="evo-tip-line">无条件</div>}
            </div>
          }
        >
          <span className="evo-cond-chip">{conditionLabel(c)}</span>
        </Tooltip>
      ))}
    </div>
  )
}

function NodeView({ node, current, onPick }) {
  const isCur = node.species === current
  const clickable = !!onPick && !!node.pokemon_id
  return (
    <div className="evo-branch">
      <div
        className={`evo-node${isCur ? ' evo-node-cur' : ''}${clickable ? ' evo-node-link' : ''}`}
        onClick={clickable ? () => onPick(node) : undefined}
        role={clickable ? 'button' : undefined}
        tabIndex={clickable ? 0 : undefined}
        onKeyDown={
          clickable
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') onPick(node)
              }
            : undefined
        }
      >
        <PokemonAvatar
          src={node.image_url}
          name={node.name_zh || node.species}
          alt={node.species}
          size={44}
        />
        <div className="evo-node-text">
          <span className="evo-node-zh">{node.name_zh || node.species}</span>
          <span className="evo-node-en">{node.species}</span>
        </div>
      </div>
      {node.children?.length > 0 && (
        <div className="evo-subtree">
          {node.children.map((child, i) => (
            <div className="evo-edge" key={`${child.species}-${i}`}>
              <span className="evo-arrow" aria-hidden="true">
                →
              </span>
              <ConditionChips conditions={child.conditions} />
              <NodeView node={child} current={current} onPick={onPick} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * 进化链组件。
 * variant="v"：垂直缩进布局，供抽屉内嵌（迷你版）；
 * variant="h"：水平链路布局，供弹层/详情区全宽展示，超宽可横向滚动。
 */
export default function EvolutionChain({ data, current, loading, onPick, variant = 'v' }) {
  if (loading) {
    return (
      <div className="evo-loading">
        <Spin size="small" />
      </div>
    )
  }
  if (!data?.roots?.length) {
    return <Empty description="暂无进化数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  const single = (data.total_nodes ?? 0) <= 1
  return (
    <div className={`evo-tree evo-tree--${variant}`}>
      {data.roots.map((root, i) => (
        <NodeView key={root.species || i} node={root} current={current} onPick={onPick} />
      ))}
      {single && <div className="evo-single-hint">该宝可梦没有已发现的进化形态</div>}
    </div>
  )
}
