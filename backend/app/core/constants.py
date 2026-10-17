"""常量：属性配色与中文名（前后端共用同一份定义）。"""

from __future__ import annotations

TYPE_INFO: dict[str, dict[str, str]] = {
    "normal": {"zh": "一般", "color": "#A8A878"},
    "fighting": {"zh": "格斗", "color": "#C03028"},
    "flying": {"zh": "飞行", "color": "#A890F0"},
    "poison": {"zh": "毒", "color": "#A040A0"},
    "ground": {"zh": "地面", "color": "#E0C068"},
    "rock": {"zh": "岩石", "color": "#B8A038"},
    "bug": {"zh": "虫", "color": "#A8B820"},
    "ghost": {"zh": "幽灵", "color": "#705898"},
    "steel": {"zh": "钢", "color": "#B8B8D0"},
    "fire": {"zh": "火", "color": "#F08030"},
    "water": {"zh": "水", "color": "#6890F0"},
    "grass": {"zh": "草", "color": "#78C850"},
    "electric": {"zh": "电", "color": "#F8D030"},
    "psychic": {"zh": "超能力", "color": "#F85888"},
    "ice": {"zh": "冰", "color": "#98D8D8"},
    "dragon": {"zh": "龙", "color": "#7038F8"},
    "dark": {"zh": "恶", "color": "#705848"},
    "fairy": {"zh": "妖精", "color": "#EE99AC"},
}

TYPE_ORDER: list[str] = list(TYPE_INFO.keys())

STAT_INFO: dict[str, str] = {
    "hp": "HP",
    "attack": "攻击",
    "defense": "防御",
    "special_attack": "特攻",
    "special_defense": "特防",
    "speed": "速度",
}

STAT_ORDER: list[str] = list(STAT_INFO.keys())

METRIC_OPTIONS: dict[str, str] = {
    "stat_total": "种族值总和",
    "hp": "HP",
    "attack": "攻击",
    "defense": "防御",
    "special_attack": "特攻",
    "special_defense": "特防",
    "speed": "速度",
    "height": "身高",
    "weight": "体重",
    "base_experience": "基础经验值",
}
