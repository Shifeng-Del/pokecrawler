"""媒体外链 CDN 改写测试：helper 纯函数 / schemas validator / 读出口径集成。

背景：DB 忠实保存 raw.githubusercontent.com 原始 URL，改写只发生在读出口径
（API 响应 / 统计聚合 / 数据导出），详见 app/utils/media_url.py。
"""

from __future__ import annotations

from sqlalchemy import select

from app.api.v1.pokemon import _to_out
from app.core.aggregations import ranking
from app.core.models import Pokemon
from app.core.repository import bulk_upsert
from app.core.schemas import EvolutionNodeOut, PokemonOut
from app.crawler.adapters.pokeapi import PokeAPIAdapter
from app.services.export_service import iter_csv
from app.utils.media_url import to_cdn_url
from config.settings import get_settings

# helper 单测显式传 template，与 settings 解耦
JSDELIVR = "https://cdn.jsdelivr.net/gh/{owner}/{repo}@{ref}/{path}"

SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
CRIES = "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/25.ogg"
SPRITES_CDN = "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/sprites/pokemon/other/official-artwork/25.png"
CRIES_CDN = "https://cdn.jsdelivr.net/gh/PokeAPI/cries@main/cries/pokemon/latest/25.ogg"


def _raw_payload(bulbasaur_payload: dict) -> dict:
    """把 fixture 里的假 URL 换成真实的 raw.githubusercontent 外链。"""
    payload = dict(bulbasaur_payload)
    payload["sprites"] = {"other": {"official-artwork": {"front_default": SPRITES}}}
    payload["cries"] = {"latest": CRIES}
    return payload


async def _seed_raw_urls(db_session, bulbasaur_payload: dict) -> None:
    adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
    await bulk_upsert(db_session, [adapter.map_payload(_raw_payload(bulbasaur_payload))], job_id=1)


# ---------------------------------------------------------------- Part A：helper 纯函数
class TestToCdnUrl:
    def test_sprites_master_repo(self):
        assert to_cdn_url(SPRITES, JSDELIVR) == SPRITES_CDN

    def test_cries_main_repo(self):
        # 另一个仓库 cries@main：规则不硬编码仓库名，同一正则天然覆盖
        assert to_cdn_url(CRIES, JSDELIVR) == CRIES_CDN

    def test_none_and_empty_passthrough(self):
        assert to_cdn_url(None, JSDELIVR) is None
        assert to_cdn_url("", JSDELIVR) == ""
        assert to_cdn_url("   ", JSDELIVR) == "   "

    def test_other_domain_passthrough(self):
        assert to_cdn_url("https://example.com/1.png", JSDELIVR) == "https://example.com/1.png"
        assert to_cdn_url("https://pokeapi.co/api/v2/pokemon/25/", JSDELIVR) == (
            "https://pokeapi.co/api/v2/pokemon/25/"
        )

    def test_already_cdn_is_idempotent(self):
        once = to_cdn_url(SPRITES, JSDELIVR)
        assert to_cdn_url(once, JSDELIVR) == once

    def test_http_scheme_and_uppercase_host(self):
        url = "HTTP://RAW.GITHUBUSERCONTENT.COM/PokeAPI/sprites/master/sprites/pokemon/1.png"
        assert to_cdn_url(url, JSDELIVR) == "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/sprites/pokemon/1.png"

    def test_query_and_fragment_preserved(self):
        assert to_cdn_url(SPRITES + "?v=2#frag", JSDELIVR) == SPRITES_CDN + "?v=2#frag"

    def test_empty_template_disables_rewrite(self):
        assert to_cdn_url(SPRITES, "") == SPRITES

    def test_broken_template_passthrough(self):
        # 模板缺占位符 = 配置错误，透传不产坏链
        assert to_cdn_url(SPRITES, "https://cdn.example.com/{owner}/{repo}") == SPRITES

    def test_repo_root_url_passthrough(self):
        # 路径只有 /{owner}/{repo}/{ref}、无文件段，正则不命中
        url = "https://raw.githubusercontent.com/PokeAPI/sprites/master"
        assert to_cdn_url(url, JSDELIVR) == url

    def test_commit_ref_also_rewritten(self):
        url = "https://raw.githubusercontent.com/PokeAPI/sprites/a1b2c3d/sprites/pokemon/1.png"
        assert to_cdn_url(url, JSDELIVR) == "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@a1b2c3d/sprites/pokemon/1.png"


# ---------------------------------------------------------------- Part B：validator 集成
class TestSchemaValidators:
    def test_pokemon_out_rewrites_both_fields(self):
        # 走 settings 默认模板（conftest 不覆盖 MEDIA_CDN_TEMPLATE）
        out = PokemonOut(id=25, name="pikachu", image_url=SPRITES, cry_url=CRIES)
        assert out.image_url == SPRITES_CDN
        assert out.cry_url == CRIES_CDN

    def test_pokemon_out_passthrough_and_none(self):
        out = PokemonOut(id=1, name="bulbasaur", image_url="https://example.com/1.png")
        assert out.image_url == "https://example.com/1.png"
        assert out.cry_url is None

    def test_evolution_node_out_rewrites(self):
        node = EvolutionNodeOut(species="pikachu", image_url=SPRITES)
        assert node.image_url == SPRITES_CDN


# ---------------------------------------------------------------- Part C：读出口径集成
def test_to_out_rewrites_media_urls():
    # 内存构造（不落库）：NOT NULL 列不触发，_to_out 对 None 的 JSON 列有默认值兜底
    p = Pokemon(id=25, name="pikachu", image_url=SPRITES, cry_url=CRIES)
    out = _to_out(p)
    assert out.image_url == SPRITES_CDN
    assert out.cry_url == CRIES_CDN


async def test_aggregations_ranking_rewrites_image_url(db_session, bulbasaur_payload):
    await _seed_raw_urls(db_session, bulbasaur_payload)

    items = await ranking(db_session, metric="stat_total", limit=20)
    assert len(items) == 1
    assert items[0]["image_url"] == SPRITES_CDN
    # DB 里存的仍是 raw 原值：忠实源记录，改写只在读出口径
    assert await db_session.scalar(select(Pokemon.image_url)) == SPRITES


async def test_export_csv_rewrites_image_url(db_session, bulbasaur_payload):
    await _seed_raw_urls(db_session, bulbasaur_payload)

    # iter_csv 内部自建 session 读同一测试库，验证改写对导出链路生效
    chunks = [chunk async for chunk in iter_csv(select(Pokemon))]
    text = b"".join(chunks).decode("utf-8-sig")
    assert SPRITES_CDN in text
    assert "raw.githubusercontent.com" not in text
