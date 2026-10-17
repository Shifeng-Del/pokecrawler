# 招式/特性长文机翻术语表与风格指南

本文件是 `zh_texts` 管线的翻译口径，所有分批译文必须遵守，保证 17 个批次译法一致。
改口径只改本文件，然后重跑受影响的批次。

## 1. 角色与句式

| 英文 | 中文 | 说明 |
| --- | --- | --- |
| the user | 使用者 | 招式效果说明的主角，全文统一 |
| the target | 目标 | |
| This Pokémon | 该宝可梦 | 特性效果说明的主角 |
| opponent / opposing Pokémon | 对手 / 对方宝可梦 | 语境二选一，保持篇内一致 |
| switch out | 替换下场 | 不说「换下」 |
| regular damage | 常规伤害 | 与「固定伤害」相对 |
| inflict(s) / deal(s) damage | 造成伤害 | |
| has a X% chance to | 有 X% 的几率 | |
| may also | 也有可能 | 图鉴描述里用 |

## 2. 对战术语

| 英文 | 中文 |
| --- | --- |
| stage（能力等级） | 级：「攻击提升两级」「速度降低一级」 |
| raise / boost | 提升 |
| lower / drop | 降低 |
| stat stage / stat modification | 能力等级 |
| major battle（HP/攻击/防御/特攻/特防/速度） | HP、攻击、防御、特攻、特防、速度（官方译名，不译「生命值」） |
| physical / special / status move | 物理 / 特殊 / 变化招式 |
| accuracy | 命中 |
| critical hit | 击中要害 |
| same-type attack bonus（STAB） | 本属性加成 |
| weather（sun/rain/sandstorm/hail/snow） | 大晴天 / 下雨 / 沙暴 / 冰雹 / 雪天 |
| terrain | 场地（电气场地等） |
| entry hazard（Spikes/Toxic Spikes/Stealth Rock/Sticky Web） | 撒菱 / 毒菱 / 隐形岩 / 黏黏网 |
| protect | 守住 |
| substitute | 替身 |
| recharge turn | 「充能」回合（引用招式机制时加引号） |
| flinch | 畏缩 |
| confusion | 混乱 |
| trapping move | 封印招式（如挡住去路的效果说「无法替换或逃走」） |

## 3. 命名引用规则（最重要）

- **招式名**：效果文字里以引号出现的招式名，一律查 `zh_glossary.json` 的 `moves`
  命名空间换官方简体译名并加「」；查不到才保留英文并加「」。
- **特性名**：查 `abilities` 命名空间，同样官方译名。
- **属性名**：查前端/后端同源的 18 属性表（火/水/草/电…妖精）。
- **道具名**：查 ITEM_ZH / 进化道具译名表。
- **天气、场地、状态**：用上表固定译法，不自造词。

## 4. 数字与格式

- 数字、%、×、分数（1/3、1/2）原样保留。
- 效果说明（effect）是对战机制描述，用严谨书面语，杜绝口语。
- 图鉴描述（flavor）是游戏内宝可梦图鉴口吻，允许适度文学化，但仍须准确，
  不新增原文没有的设定。
- 单位：stage 译「级」不用「阶段」；turn 译「回合」。

## 5. 禁止事项

- 禁止把英文原文原样留在译文里（HP/PP/属性缩写等专有缩写除外）。
- 禁止漏译半句；长句可拆短句，但信息点一个不能少。
- 禁止自行发挥游戏机制解释（如「因为…所以很强」）。
