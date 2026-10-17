"""CSS 选择器解析器离线测试（不依赖网络）。"""

from app.crawler.parser import CSSSelectorParser, JsonPathParser

HTML = """
<html><body>
  <article class="product_pod">
    <h3><a href="catalogue/a-book.html" title="A Book">A Book</a></h3>
    <p class="price_color">£51.77</p>
  </article>
  <article class="product_pod">
    <h3><a href="catalogue/b-book.html" title="B Book">B Book</a></h3>
    <p class="price_color">£12.00</p>
  </article>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <div class="product_main"><h1>The Title</h1></div>
  <p class="price_color">£33.29</p>
  <p class="availability">In stock (7 available)</p>
</body></html>
"""


def test_css_parse_list():
    parser = CSSSelectorParser()
    rules = {
        "item": "article.product_pod",
        "fields": {
            "name": {"sel": "h3 a", "attr": "title"},
            "url": {"sel": "h3 a", "attr": "href"},
            "price": {"sel": ".price_color", "attr": "text", "regex": r"([\d.]+)", "type": "float"},
        },
    }
    items = parser.parse_list(HTML, rules)
    assert len(items) == 2
    assert items[0]["name"] == "A Book"
    assert items[0]["url"] == "catalogue/a-book.html"
    assert items[0]["price"] == 51.77
    assert items[1]["price"] == 12.0


def test_css_parse_detail_with_default():
    parser = CSSSelectorParser()
    rules = {
        "fields": {
            "name": {"sel": ".product_main h1", "attr": "text"},
            "price": {"sel": ".price_color", "attr": "text", "regex": r"([\d.]+)", "type": "float"},
            "stock": {"sel": ".availability", "attr": "text"},
            "missing": {"sel": ".none", "attr": "text", "default": "N/A"},
        }
    }
    fields = parser.parse_detail(DETAIL_HTML, rules)
    assert fields["name"] == "The Title"
    assert fields["price"] == 33.29
    assert fields["stock"].startswith("In stock")
    assert fields["missing"] == "N/A"


def test_json_path_parser():
    parser = JsonPathParser()
    rules = {"items": "results", "fields": {"name": "name", "id": "id|0"}}
    payload = {"results": [{"name": "a", "id": 1}, {"name": "b"}]}
    items = parser.parse_list(payload, rules)
    assert items[0]["name"] == "a"
    assert items[0]["id"] == 1
    assert items[1]["id"] == 0  # 默认值生效
