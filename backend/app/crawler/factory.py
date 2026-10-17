"""抓取器/解析器/适配器工厂：按配置或单次参数切换实现。"""

from __future__ import annotations

from app.crawler.base import BaseFetcher
from app.crawler.robots import RobotsPolicy
from app.crawler.throttle import build_limiter
from config.settings import Settings


class FetcherFactory:
    _registry: dict[str, str] = {
        "httpx": "app.crawler.httpx_fetcher.HttpxFetcher",
        "playwright": "app.crawler.playwright_fetcher.PlaywrightFetcher",
    }

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls._registry)

    @classmethod
    def create(
        cls,
        name: str,
        settings: Settings,
        *,
        concurrency: int | None = None,
        robots: RobotsPolicy | None = None,
    ) -> BaseFetcher:
        key = (name or settings.crawler_fetcher).lower()
        if key not in cls._registry:
            raise ValueError(f"未知抓取器：{name}，可选 {cls.available()}")

        module_path, class_name = cls._registry[key].rsplit(".", 1)
        import importlib  # noqa: PLC0415

        module = importlib.import_module(module_path)
        fetcher_cls = getattr(module, class_name)

        if concurrency is None:
            concurrency, rate, interval, _timeout = settings.fetcher_limits(key)
        else:
            _, rate, interval, _timeout = settings.fetcher_limits(key)

        limiter, semaphore = build_limiter(rate, interval, concurrency)
        return fetcher_cls(
            settings,
            robots=robots or RobotsPolicy(settings),
            limiter=limiter,
            semaphore=semaphore,
            retries=settings.crawler_retries,
        )


class ParserFactory:
    @classmethod
    def create(cls, name: str):
        from app.crawler.parser import CSSSelectorParser, JsonPathParser

        key = (name or "json").lower()
        if key == "css":
            return CSSSelectorParser()
        return JsonPathParser()


class AdapterFactory:
    @classmethod
    def create(cls, name: str, fetcher: BaseFetcher, settings: Settings):
        key = (name or "pokeapi").lower()
        if key == "pokeapi":
            from app.crawler.adapters.pokeapi import PokeAPIAdapter

            return PokeAPIAdapter(fetcher, settings)
        if key in ("generic_html", "html", "generic"):
            from app.crawler.adapters.generic_html import GenericHtmlAdapter

            return GenericHtmlAdapter(fetcher, settings)
        # P2 深度目标：与 pokemon 同源不同端点，各自独立适配器
        if key in (
            "pokeapi-species",
            "pokeapi-evolution",
            "pokeapi-move-detail",
            "pokeapi-ability-detail",
        ):
            from app.crawler.adapters import pokeapi as _pokeapi

            adapter_cls = {
                "pokeapi-species": _pokeapi.SpeciesAdapter,
                "pokeapi-evolution": _pokeapi.EvolutionAdapter,
                "pokeapi-move-detail": _pokeapi.MoveDetailAdapter,
                "pokeapi-ability-detail": _pokeapi.AbilityDetailAdapter,
            }[key]
            return adapter_cls(fetcher, settings)
        raise ValueError(f"未知适配器：{name}")
