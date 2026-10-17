/** 属性配色与中文名（与后端 constants.py 保持同源） */

export const TYPE_INFO = {
  normal: { zh: '一般', color: '#A8A878' },
  fighting: { zh: '格斗', color: '#C03028' },
  flying: { zh: '飞行', color: '#A890F0' },
  poison: { zh: '毒', color: '#A040A0' },
  ground: { zh: '地面', color: '#E0C068' },
  rock: { zh: '岩石', color: '#B8A038' },
  bug: { zh: '虫', color: '#A8B820' },
  ghost: { zh: '幽灵', color: '#705898' },
  steel: { zh: '钢', color: '#B8B8D0' },
  fire: { zh: '火', color: '#F08030' },
  water: { zh: '水', color: '#6890F0' },
  grass: { zh: '草', color: '#78C850' },
  electric: { zh: '电', color: '#F8D030' },
  psychic: { zh: '超能力', color: '#F85888' },
  ice: { zh: '冰', color: '#98D8D8' },
  dragon: { zh: '龙', color: '#7038F8' },
  dark: { zh: '恶', color: '#705848' },
  fairy: { zh: '妖精', color: '#EE99AC' },
}

export const TYPE_OPTIONS = Object.entries(TYPE_INFO).map(([name, info]) => ({
  value: name,
  label: info.zh,
  color: info.color,
}))

export const STAT_LABEL = {
  hp: 'HP',
  attack: '攻击',
  defense: '防御',
  special_attack: '特攻',
  special_defense: '特防',
  speed: '速度',
}

export const STAT_ORDER = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']

export const METRIC_OPTIONS = [
  { value: 'stat_total', label: '种族值总和' },
  { value: 'hp', label: 'HP' },
  { value: 'attack', label: '攻击' },
  { value: 'defense', label: '防御' },
  { value: 'special_attack', label: '特攻' },
  { value: 'special_defense', label: '特防' },
  { value: 'speed', label: '速度' },
  { value: 'height', label: '身高' },
  { value: 'weight', label: '体重' },
  { value: 'base_experience', label: '基础经验值' },
]

export const typeZh = (name) => TYPE_INFO[name]?.zh || name || '—'
export const typeColor = (name) => TYPE_INFO[name]?.color || '#8c8c8c'

/** 后端 stats 字典的 key 是 special-attack，前端统一用下划线 */
export function normalizeStats(stats = {}) {
  return {
    hp: stats.hp ?? 0,
    attack: stats.attack ?? 0,
    defense: stats.defense ?? 0,
    special_attack: stats['special-attack'] ?? stats.special_attack ?? 0,
    special_defense: stats['special-defense'] ?? stats.special_defense ?? 0,
    speed: stats.speed ?? 0,
  }
}

/** 身高单位 dm → m，体重单位 hg → kg */
export const toMeters = (dm) => (dm ? dm / 10 : 0)
export const toKg = (hg) => (hg ? hg / 10 : 0)

/* ---------------------------------------------------------------- P2 封闭枚举中文
 * 与后端 zh_glossary.json 的同名命名空间保持同源（egg-groups/habitats/colors/
 * shapes/growth-rates/evolution-trigger）。查不到一律回退英文 slug。
 * P3 的进化链组件、招式图鉴页、图鉴分类筛选直接复用。 */
export const EGG_GROUP_ZH = {
  monster: '怪兽',
  water1: '水中1',
  water2: '水中2',
  water3: '水中3',
  bug: '虫',
  flying: '飞行',
  ground: '地上',
  fairy: '妖精',
  plant: '植物',
  humanshape: '人形',
  mineral: '矿物',
  indeterminate: '不定形',
  ditto: '百变怪',
  dragon: '龙',
  'no-eggs': '未发现',
}

export const HABITAT_ZH = {
  cave: '洞穴',
  forest: '森林',
  grassland: '草原',
  mountain: '山地',
  rare: '稀有',
  'rough-terrain': '恶劣地形',
  sea: '海洋',
  urban: '城镇',
  'waters-edge': '水边',
}

export const COLOR_ZH = {
  black: '黑',
  blue: '蓝',
  brown: '棕',
  gray: '灰',
  green: '绿',
  pink: '粉红',
  purple: '紫',
  red: '红',
  white: '白',
  yellow: '黄',
}

export const SHAPE_ZH = {
  ball: '球形',
  squiggle: '蛇形',
  fish: '鱼形',
  arms: '手臂形',
  blob: '软体形',
  upright: '直立形',
  legs: '腿形',
  quadruped: '四足形',
  wings: '有翼形',
  tentacles: '触手形',
  heads: '多头形',
  humanoid: '人形',
  'bug-wings': '虫翅形',
  armor: '铠甲形',
}

export const GROWTH_RATE_ZH = {
  slow: '缓慢',
  medium: '中等',
  fast: '快速',
  'medium-slow': '中等偏慢',
  'slow-then-very-fast': '先慢后快',
  'fast-then-very-slow': '先快后慢',
}

export const EVOLUTION_TRIGGER_ZH = {
  'level-up': '升级',
  trade: '通信交换',
  'use-item': '使用道具',
  shed: '蜕皮',
  spin: '旋转',
  'tower-of-darkness': '暗之塔',
  'tower-of-waters': '水之塔',
  'three-critical-hits': '三次击中要害',
  'take-damage': '受到伤害',
  'in-battle-level-up': '对战中升级',
  'agile-style-move': '灵巧风格招式',
  'strong-style-move': '刚猛风格招式',
  'recoil-damage': '反作用力伤害',
  'use-move': '使用招式',
  'three-defeated-bisharp': '击败三只首领狃哈兽',
  'gimmighoul-coins': '收集金币',
  'meltan-candies': '美录坦糖果',
  unclassified: '未分类',
}

/** 通用查表：命中返回中文，未命中回退英文（绝不给英文套中文壳） */
export const zhOf = (map, name) => (name ? map[name] || name : '—')

/* ---------------------------------------------------------------- P3 进化道具中文
 * PokeAPI evolution_edge.item 列的全部取值（26 个进化相关道具）。
 * 官方译名（火之石/月之石等），查不到回退英文 slug。 */
export const ITEM_ZH = {
  'fire-stone': '火之石',
  'water-stone': '水之石',
  'thunder-stone': '雷之石',
  'leaf-stone': '叶之石',
  'moon-stone': '月之石',
  'sun-stone': '日之石',
  'shiny-stone': '光之石',
  'dusk-stone': '暗之石',
  'dawn-stone': '觉醒之石',
  'ice-stone': '冰之石',
  'sweet-apple': '甜蜜苹果',
  'tart-apple': '酸酸苹果',
  'syrupy-apple': '糖霜苹果',
  'chipped-pot': '缺口壶',
  'cracked-pot': '裂纹壶',
  'unremarkable-teacup': '平凡茶杯',
  'masterpiece-teacup': '杰作茶杯',
  'auspicious-armor': '吉兆装甲',
  'malicious-armor': '凶兆装甲',
  'black-augurite': '黑奇石',
  'galarica-cuff': '伽勒豆蔻手环',
  'galarica-wreath': '伽勒豆蔻花环',
  'metal-alloy': '金属合金',
  'peat-block': '泥炭块',
  'scroll-of-darkness': '暗黑卷轴',
  'scroll-of-waters': '水润卷轴',
  /* 以下为通信交换进化时「携带的道具」（detail_json.held_item），与上方进化道具同源 */
  'berry-sweet': '浆果糖',
  'clover-sweet': '三叶糖',
  'deep-sea-scale': '深海鳞片',
  'deep-sea-tooth': '深海之牙',
  'dragon-scale': '龙之鳞片',
  'dubious-disc': '怪异补丁',
  'electirizer': '电力增幅器',
  'flower-sweet': '花朵糖',
  'kings-rock': '王者之证',
  'love-sweet': '爱心糖',
  'magmarizer': '熔岩增幅器',
  'metal-coat': '金属膜',
  'oval-stone': '浑圆之石',
  'prism-scale': '美丽鳞片',
  'protector': '护具',
  'razor-claw': '锐利之爪',
  'razor-fang': '锐利獠牙',
  'reaper-cloth': '灵界之布',
  'ribbon-sweet': '蝴蝶结糖',
  'sachet': '香袋',
  'star-sweet': '星星糖',
  'strawberry-sweet': '草莓糖',
  'up-grade': '升级资料',
  'whipped-dream': '泡沫奶油',
}

/** 进化地点（detail_json.location，如伊布叶/冰进化、自爆磁磁场地） */
export const LOCATION_ZH = {
  'blush-mountain': '红润山',
  'chargestone-cave': '电石洞窟',
  'dusty-bowl': '尘埃盆地',
  'eterna-forest': '百代森林',
  'frost-cavern': '冰结洞窟',
  'kalos-route-13': '卡洛斯13号道路',
  'kalos-route-20': '卡洛斯20号道路',
  'lush-jungle': '繁茂丛林',
  'mount-lanakila': '拉纳基拉山',
  'mt-coronet': '天冠山',
  'new-mauville': '新紫堇',
  'petalburg-woods': '橙华森林',
  'pinwheel-forest': '风车森林',
  'shoal-cave': '浅滩洞穴',
  'sinnoh-route-217': '神奥217号道路',
  'twist-mountain': '旋风山',
  'vast-poni-canyon': '波尼大峡谷',
}

/** 性格（颤弦蝾螈的高/低调形态进化按性格分流） */
export const NATURE_ZH = {
  adamant: '固执',
  bashful: '害羞',
  bold: '大胆',
  brave: '勇敢',
  calm: '沉着',
  careful: '慎重',
  docile: '坦率',
  gentle: '温和',
  hardy: '勤奋',
  hasty: '急躁',
  impish: '淘气',
  jolly: '爽朗',
  lax: '乐天',
  lonely: '怕寂寞',
  mild: '慢吞吞',
  modest: '内敛',
  naive: '天真',
  naughty: '顽皮',
  quiet: '冷静',
  quirky: '浮躁',
  rash: '马虎',
  relaxed: '悠闲',
  sassy: '自大',
  serious: '认真',
  timid: '胆小',
}

/** 招式伤害类别（move_detail.damage_class） */
export const DAMAGE_CLASS_INFO = {
  physical: { zh: '物理', color: '#C03028' },
  special: { zh: '特殊', color: '#4D70D4' },
  status: { zh: '变化', color: '#8A8A8A' },
}
export const damageClassZh = (name) => DAMAGE_CLASS_INFO[name]?.zh || name || '—'
export const damageClassColor = (name) => DAMAGE_CLASS_INFO[name]?.color || '#8A8A8A'

/** 一天中的时段（evolution_edge.time_of_day） */
export const TIME_OF_DAY_ZH = {
  day: '白天',
  night: '夜晚',
  dusk: '黄昏',
  'full-moon': '满月',
}

/** 世代 slug → 中文（move_detail / ability_detail / species.generation） */
export const GENERATION_ZH = {
  'generation-i': '第一世代',
  'generation-ii': '第二世代',
  'generation-iii': '第三世代',
  'generation-iv': '第四世代',
  'generation-v': '第五世代',
  'generation-vi': '第六世代',
  'generation-vii': '第七世代',
  'generation-viii': '第八世代',
  'generation-ix': '第九世代',
}
export const generationZh = (name) => GENERATION_ZH[name] || name || '—'
