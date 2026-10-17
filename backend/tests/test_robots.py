from urllib.robotparser import RobotFileParser

from app.crawler.robots import RobotsPolicy
from config.settings import get_settings


def _parser(text: str) -> RobotFileParser:
    p = RobotFileParser()
    p.parse(text.splitlines())
    return p


class _FakePolicy(RobotsPolicy):
    def __init__(self, text: str):
        super().__init__(get_settings())
        self._text = text

    async def _load(self, url):  # type: ignore[override]
        return _parser(self._text)


async def test_disallow_is_respected():
    policy = _FakePolicy(
        "User-agent: *\nDisallow: /private/\nAllow: /api/\n"
    )
    assert await policy.can_fetch("https://x.com/api/v2/pokemon/1/", "UA") is True
    assert await policy.can_fetch("https://x.com/private/secret", "UA") is False


async def test_all_disallow_blocks_everything():
    policy = _FakePolicy("User-agent: *\nDisallow: /\n")
    assert await policy.can_fetch("https://x.com/anything", "UA") is False


async def test_crawl_delay_parsed():
    policy = _FakePolicy("User-agent: *\nCrawl-delay: 2\n")
    assert await policy.crawl_delay("https://x.com/a", "UA") == 2.0


async def test_error_policy_deny_blocks_when_unreachable():
    class _Broken(RobotsPolicy):
        async def _load(self, url):  # type: ignore[override]
            return None

    settings = get_settings()
    original = settings.robots_on_error
    try:
        settings.robots_on_error = "deny"
        assert await _Broken(settings).can_fetch("https://x.com/a", "UA") is False
        settings.robots_on_error = "allow"
        assert await _Broken(settings).can_fetch("https://x.com/a", "UA") is True
    finally:
        settings.robots_on_error = original
