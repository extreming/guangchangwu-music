from app.parsers import huoshan, kuaishou
from app.parsers.linktext import extract_urls
from app.parsers.registry import choose_url


def test_douyin_share_text():
    text = "7.64 aFu:/ 复制打开抖音，看看【李阿姨的作品】老街的雨声 https://v.douyin.com/iJabc123/ "
    assert extract_urls(text) == ["https://v.douyin.com/iJabc123/"]


def test_kuaishou_share_text():
    text = "https://v.kuaishou.com/abcd12 看了这么多快手，还是「王叔」拍得最好！"
    assert extract_urls(text) == ["https://v.kuaishou.com/abcd12"]
    assert kuaishou.matches(extract_urls(text)[0])


def test_huoshan_share_text():
    text = "复制此链接，打开【抖音火山版】，直接观看视频！ https://share.huoshan.com/hotsoon/s/AbC123/"
    urls = extract_urls(text)
    assert urls == ["https://share.huoshan.com/hotsoon/s/AbC123/"]
    assert huoshan.matches(urls[0])


def test_zero_width_and_trailing_punctuation():
    text = "前面\u200bhttps://www.douyin.com/video/7123456789012345678\u200b。后面"
    assert extract_urls(text) == ["https://www.douyin.com/video/7123456789012345678"]
    assert extract_urls("看 https://v.douyin.com/abc/.") == ["https://v.douyin.com/abc/"]


def test_no_url():
    assert extract_urls("今天一起跳舞") == []
    assert extract_urls("") == []


def test_choose_known_platform_over_other_links():
    urls = extract_urls("说明 https://example.com/a 真的 https://v.kuaishou.com/abc")
    assert choose_url(urls) == "https://v.kuaishou.com/abc"
