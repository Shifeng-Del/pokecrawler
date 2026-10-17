"""P3 前端数据消费验收：分类筛选 / 进化链组装 / 招式图鉴 / 特性明细。

与 P1/P2 的分工：P1 测前端 DOM，P2 测数据库，本脚本测「前端消费的 API 契约」。
以 ASGI Transport 直接驱动真实应用 + 真实数据库（全部为只读查询，不写库），
无需启动 uvicorn，也不触碰测试库。

用法：
    python scripts/verify_p3.py
    python scripts/verify_p3.py --strict   # 有任何 FAIL 时退出码 1
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "data" / "poke.db"

# 必须在导入任何 app 模块之前设置：settings 在导入时即实例化缓存
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH.as_posix()}")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
sys.path.insert(0, str(BACKEND_DIR))

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()

from fastapi.testclient import TestClient  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="P3 接口验收")
    ap.add_argument("--strict", action="store_true")
    ap.parse_args()

    if not DB_PATH.exists():
        print(f"[错误] 数据库不存在：{DB_PATH}，先完成 P2 爬取")
        return 1

    from app.main import app

    with TestClient(app) as client:
        # ---------- 1. 分类筛选项 ----------
        print("== 分类筛选项 ==")
        resp = client.get("/api/v1/pokemon/filter-options")
        check("filter-options 200", resp.status_code == 200)
        opts = resp.json()
        for key in ("genus", "egg_groups", "habitats", "colors", "shapes", "growth_rates"):
            items = opts.get(key) or []
            check(f"{key} 非空", len(items) >= 5, f"{len(items)} 项")
        genus = {g["value"]: g for g in opts["genus"]}
        seed = genus.get("Seed Pokémon")
        check("genus 含种子宝可梦", bool(seed) and "种子" in seed["label"], str(seed and seed["label"]))
        check("genus 计数口径（形态级）", bool(seed) and seed["count"] >= 3, f"count={seed and seed['count']}")
        for dim, value in (
            ("egg_groups", "monster"),
            ("habitats", "grassland"),
            ("colors", "red"),
            ("shapes", "ball"),
            ("growth_rates", "medium-slow"),
        ):
            hit = any(o["value"] == value for o in opts[dim])
            check(f"{dim} 含 {value}", hit)

        # ---------- 2. 筛选联动（期望值为 2026-10 快照） ----------
        print("== 物种分类筛选联动 ==")
        # 期望值均为「形态级」计数（含 Mega/太晶等替换形态），
        # 已用 SQL 直连核对；type 筛选匹配任一属性槽位（主/副属性都算）
        cases = [
            ({"genus": "Seed Pokémon"}, 6, "genus=Seed Pokémon"),
            ({"egg_group": "monster"}, 111, "egg_group=monster"),
            ({"habitat": "waters-edge"}, 61, "habitat=waters-edge"),
            ({"shape": "ball", "color": "red"}, 12, "shape=ball&color=red"),
            # 形态级计数：medium-slow 物种 261、含替换形态 336
            ({"growth_rate": "medium-slow"}, 336, "growth_rate=medium-slow"),
        ]
        for query, expected, label in cases:
            resp = client.get("/api/v1/pokemon", params=query)
            body = resp.json()
            check(f"筛选 {label}", resp.status_code == 200 and body["total"] == expected,
                  f"total={body.get('total')}")

        # 组合筛选应收窄结果
        base = client.get("/api/v1/pokemon", params={"habitat": "grassland"}).json()["total"]
        combo = client.get(
            "/api/v1/pokemon", params={"habitat": "grassland", "type": "grass"}
        ).json()["total"]
        check("组合筛选收窄（habitat+type）", 0 < combo < base, f"{base} → {combo}")
        fire_grassland = client.get(
            "/api/v1/pokemon", params={"habitat": "grassland", "type": "fire"}
        ).json()
        # 草原里确实住着火系（小火马/烈焰马一族，含替换形态），不为空但远小于草原总数
        check(
            "矛盾组合正确收窄（草原+火=19）",
            fire_grassland["total"] == 19 and fire_grassland["total"] < base,
            f"total={fire_grassland['total']}",
        )

        # ---------- 3. 进化链 ----------
        print("== 进化链组装 ==")
        resp = client.get("/api/v1/pokemon/bulbasaur/evolution")
        body = resp.json()
        root = body["roots"][0] if body.get("roots") else {}
        ivy = (root.get("children") or [{}])[0]
        ven = (ivy.get("children") or [{}])[0]
        cond = (ivy.get("conditions") or [{}])[0]
        check(
            "bulbasaur 三段链（16/32）",
            resp.status_code == 200
            and body["total_nodes"] == 3
            and root.get("species") == "bulbasaur"
            and ivy.get("species") == "ivysaur"
            and cond.get("min_level") == 16
            and ven.get("species") == "venusaur"
            and (ven.get("conditions") or [{}])[0].get("min_level") == 32,
        )
        check(
            "节点带代表形态 id",
            all(n.get("pokemon_id") for n in (root, ivy, ven)),
            f"{root.get('pokemon_id')}/{ivy.get('pokemon_id')}/{ven.get('pokemon_id')}",
        )
        check(
            "条件带中文触发名",
            cond.get("trigger") == "level-up" and bool(cond.get("trigger_zh")),
            str(cond.get("trigger_zh")),
        )

        eevee = client.get("/api/v1/pokemon/eevee/evolution").json()
        kids = {c["species"]: c for c in (eevee["roots"][0].get("children") or [])}
        check("伊布 8 分支", len(kids) == 8, f"{len(kids)} 个进化")
        check(
            "水伊布带水之石条件",
            bool(kids.get("vaporeon", {}).get("conditions", [{}])[0].get("item") == "water-stone"),
        )

        # 皮卡丘家族链根在皮丘：整棵树应同时包含皮丘/皮卡丘/雷丘
        pikachu = client.get("/api/v1/pokemon/pikachu/evolution").json()

        def all_species(node):
            out = {node["species"]}
            for c in node.get("children") or []:
                out |= all_species(c)
            return out

        tree = set()
        for r in pikachu["roots"]:
            tree |= all_species(r)
        check("皮卡丘家族链（皮丘→皮卡丘→雷丘）", {"pichu", "pikachu", "raichu"} <= tree, str(sorted(tree)))

        # 百变怪确实没有任何进化边
        ditto = client.get("/api/v1/pokemon/ditto/evolution").json()
        check(
            "百变怪单节点（无进化）",
            ditto["total_nodes"] == 1 and not ditto["roots"][0]["children"],
        )
        check("未知物种 404", client.get("/api/v1/pokemon/not-a-pokemon/evolution").status_code == 404)

        # ---------- 4. 招式图鉴 ----------
        print("== 招式图鉴 ==")
        moves = client.get("/api/v1/moves", params={"page_size": 50}).json()
        check("招式总数 937", moves["total"] == 937, f"total={moves['total']}")
        powers = [m["power"] for m in moves["items"] if m["power"] is not None]
        check("默认按威力降序", powers == sorted(powers, reverse=True), f"top={powers[0]}")
        check("首招大爆炸 250", moves["items"][0]["name"] == "explosion" and moves["items"][0]["power"] == 250)

        grass_special = client.get(
            "/api/v1/moves", params={"type_name": "grass", "damage_class": "special"}
        ).json()
        check(
            "属性+类别组合筛选",
            grass_special["total"] > 0
            and all(m["type_name"] == "grass" and m["damage_class"] == "special" for m in grass_special["items"]),
            f"total={grass_special['total']}",
        )
        status = client.get("/api/v1/moves", params={"damage_class": "status", "page_size": 20}).json()
        # 变化招式威力为 0 或 NULL（如胜利之舞 power=0），展示层一律按「—」处理
        check("变化招式无威力", all(m["power"] in (None, 0) for m in status["items"]))
        zh_search = client.get("/api/v1/moves", params={"q": "撞击"}).json()
        check(
            "中文搜索命中撞击",
            [m["name"] for m in zh_search["items"]] == ["tackle"]
            and zh_search["items"][0]["name_zh"] == "撞击",
        )
        batch = client.get(
            "/api/v1/moves", params={"names": "tackle,growl,thunderbolt,swift"}
        ).json()
        check(
            "批量查询（悬停明细用）",
            batch["total"] == 4 and {m["name"] for m in batch["items"]} == {"tackle", "growl", "thunderbolt", "swift"},
        )

        detail = client.get("/api/v1/moves/tackle").json()
        check(
            "撞击明细 40/100/35/0",
            (detail["power"], detail["accuracy"], detail["pp"], detail["priority"]) == (40, 100, 35, 0)
            and detail["damage_class"] == "physical"
            and detail["type_name"] == "normal",
        )
        check(
            "学会人数与效果文",
            detail["learner_count"] > 400 and bool(detail.get("effect_en")),
            f"learner={detail['learner_count']}",
        )
        check("未知招式 404", client.get("/api/v1/moves/not-a-move").status_code == 404)

        # ---------- 5. 特性明细 ----------
        print("== 特性明细 ==")
        ability = client.get("/api/v1/abilities/overgrow").json()
        check(
            "茂盛效果与持有数",
            bool(ability.get("effect_en")) and ability["holder_count"] > 0,
            f"holders={ability['holder_count']}",
        )
        ab_batch = client.get("/api/v1/abilities", params={"names": "overgrow,chlorophyll"}).json()
        check("特性批量查询", ab_batch["total"] == 2)
        check("未知特性 404", client.get("/api/v1/abilities/not-an-ability").status_code == 404)

        # ---------- 6. 中文覆盖（报告项） ----------
        print("== 中文覆盖（报告） ==")
        import json

        glossary = json.loads((BACKEND_DIR / "app" / "data" / "zh_glossary.json").read_text(encoding="utf-8"))
        move_zh = glossary.get("moves") or {}
        all_moves = client.get("/api/v1/moves", params={"page_size": 200}).json()
        total_moves = all_moves["total"]
        covered = len(move_zh)
        print(f"  招式译名覆盖：{covered}/{total_moves}（余下为 Z 招/极巨/暗影招式，无官方译名把握，保留英文回落）")
        check("招式译名覆盖 >= 840", covered >= 840, f"{covered}")

    total = len(PASSED) + len(FAILED)
    print(f"\nP3 验收：{len(PASSED)}/{total} 通过" + (f"，{len(FAILED)} 项失败" if FAILED else ""))
    if FAILED:
        for name in FAILED:
            print(f"  FAIL  {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
