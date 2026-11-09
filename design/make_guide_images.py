"""Draw the large step pictures used in the mini program. Re-run after copy changes."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "miniprogram" / "images"
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"

PAPER = (255, 246, 234)
INK = (26, 26, 26)
GREEN = (6, 78, 59)
MINT = (229, 246, 236)
WHITE = (255, 255, 255)
ORANGE = (224, 122, 61)
GOLD = (255, 224, 138)
MUTED = (90, 84, 74)
BLUE = (11, 58, 110)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size, index=0)


def text_size(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=face)
    return box[2] - box[0], box[3] - box[1]


def new_card() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (900, 680), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 10, 889, 669), radius=32, outline=GREEN, width=8)
    return image, draw


def header(draw: ImageDraw.ImageDraw, number: str, lines: list[str]) -> None:
    draw.ellipse((36, 32, 132, 128), fill=GREEN)
    face = font(56)
    width, height = text_size(draw, number, face)
    draw.text((84 - width / 2, 80 - height / 2 - 6), number, font=face, fill=WHITE)
    face = font(40)
    top = 36
    for line in lines:
        draw.text((156, top), line, font=face, fill=INK)
        draw.text((158, top), line, font=face, fill=INK)
        top += 52


def phone_screen(draw: ImageDraw.ImageDraw, fill: tuple[int, int, int] = WHITE) -> tuple[int, int, int, int]:
    x, y, w, h = 150, 168, 600, 460
    draw.rounded_rectangle((x, y, x + w, y + h), radius=40, fill=fill, outline=INK, width=7)
    draw.rounded_rectangle((x + w / 2 - 40, y + 16, x + w / 2 + 40, y + 30), radius=6, fill=INK)
    return (x + 24, y + 52, w - 48, h - 78)


def finger(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    draw.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), fill=ORANGE)
    draw.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), outline=WHITE, width=4)
    draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=WHITE)


def label_button(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    fill: tuple[int, int, int],
    text_fill: tuple[int, int, int],
    mark: bool = False,
) -> None:
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), radius=22, fill=fill)
    gutter = 84 if mark else 28
    size = 36
    face = font(size)
    while size > 22:
        face = font(size)
        width, _height = text_size(draw, label, face)
        if width <= w - gutter - 28:
            break
        size -= 2
    _width, height = text_size(draw, label, face)
    draw.text((x + 22, y + (h - height) / 2 - 2), label, font=face, fill=text_fill)
    if mark:
        finger(draw, x + w - 42, y + h / 2)


def footer(draw: ImageDraw.ImageDraw) -> None:
    face = font(26)
    text = "示意图"
    width, _height = text_size(draw, text, face)
    draw.text((860 - width, 628), text, font=face, fill=GREEN)


def save(image: Image.Image, relative: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def flow_share() -> None:
    image, draw = new_card()
    header(draw, "1", ["打开抖音或快手", "点下面的「分享」"])
    sx, sy, sw, sh = phone_screen(draw, WHITE)
    draw.rectangle((sx, sy + sh - 120, sx + sw, sy + sh), fill=MINT)
    label_button(draw, (sx + 28, sy + sh - 100, sw - 56, 78), "分享", GREEN, WHITE, mark=True)
    footer(draw)
    save(image, "flow/share.png")


def flow_copy() -> None:
    image, draw = new_card()
    header(draw, "2", ["在弹出来的框里", "点「复制链接」"])
    sx, sy, sw, sh = phone_screen(draw, (244, 241, 236))
    panel_top = sy + 70
    draw.rounded_rectangle((sx + 16, panel_top, sx + sw - 16, sy + sh - 16), radius=24, fill=WHITE)
    rows = [("发给朋友", False), ("复制链接", True), ("收藏", False)]
    y = panel_top + 28
    for text, hot in rows:
        fill = GREEN if hot else WHITE
        color = WHITE if hot else MUTED
        label_button(draw, (sx + 28, y, sw - 56, 78), text, fill, color, mark=hot)
        y += 96
    footer(draw)
    save(image, "flow/copy.png")


def flow_paste() -> None:
    image, draw = new_card()
    header(draw, "3", ["回到「广场舞音乐」", "点绿色「粘贴链接」"])
    sx, sy, sw, sh = phone_screen(draw, PAPER)
    face = font(28)
    draw.text((sx + 24, sy + 36), "广场舞音乐", font=face, fill=GREEN)
    label_button(draw, (sx + 24, sy + 120, sw - 48, 96), "粘贴链接", GREEN, WHITE, mark=True)
    label_button(draw, (sx + 24, sy + 240, sw - 48, 96), "提取音乐", GREEN, WHITE)
    footer(draw)
    save(image, "flow/paste.png")


def guide_step1() -> None:
    image, draw = new_card()
    header(draw, "1", ["点这个绿色按钮", "「发给文件传输助手」"])
    sx, sy, sw, sh = phone_screen(draw, PAPER)
    label_button(draw, (sx + 18, sy + 150, sw - 36, 110), "发给文件传输助手", GREEN, WHITE, mark=True)
    footer(draw)
    save(image, "guide/step1.png")


def guide_step2() -> None:
    image, draw = new_card()
    header(draw, "2", ["找到这一行", "点「文件传输助手」"])
    sx, sy, sw, sh = phone_screen(draw, WHITE)
    rows = [("最近聊天", False), ("文件传输助手", True), ("家庭群", False)]
    y = sy + 40
    for text, hot in rows:
        fill = GREEN if hot else (245, 245, 245)
        color = WHITE if hot else INK
        label_button(draw, (sx + 16, y, sw - 32, 86), text, fill, color, mark=hot)
        y += 108
    footer(draw)
    save(image, "guide/step2.png")


def guide_step3() -> None:
    image, draw = new_card()
    header(draw, "3", ["打开聊天以后", "点一下这个音乐"])
    sx, sy, sw, sh = phone_screen(draw, (236, 246, 240))
    card_top = sy + 130
    draw.rounded_rectangle((sx + 24, card_top, sx + sw - 24, card_top + 150), radius=20, fill=WHITE, outline=GREEN, width=5)
    draw.text((sx + 48, card_top + 18), "♪  夕阳红.mp3", font=font(36), fill=INK)
    draw.text((sx + 48, card_top + 78), "点这个文件", font=font(30), fill=GREEN)
    finger(draw, sx + sw - 90, card_top + 168)
    footer(draw)
    save(image, "guide/step3.png")


def guide_android4() -> None:
    image, draw = new_card()
    header(draw, "4", ["点「保存」", "音乐就留在手机里"])
    sx, sy, sw, sh = phone_screen(draw, (244, 241, 236))
    y = sy + 90
    for text, hot in (("保存", True), ("用其他应用打开", False), ("取消", False)):
        fill = GREEN if hot else WHITE
        color = WHITE if hot else INK
        label_button(draw, (sx + 24, y, sw - 48, 84), text, fill, color, mark=hot)
        y += 102
    footer(draw)
    save(image, "guide/android4.png")


def guide_ios4() -> None:
    image, draw = new_card()
    header(draw, "4", ["点「用其他应用打开」", "再点「存储到文件」"])
    sx, sy, sw, _sh = phone_screen(draw, (244, 241, 236))
    label_button(draw, (sx + 20, sy + 36, sw - 40, 86), "用其他应用打开", GREEN, WHITE, mark=True)
    draw.text((sx + 28, sy + 146), "然后点", font=font(28), fill=MUTED)
    label_button(draw, (sx + 20, sy + 196, sw - 40, 90), "存储到“文件”", BLUE, WHITE, mark=True)
    footer(draw)
    save(image, "guide/ios4.png")


def guide_browser() -> None:
    image, draw = new_card()
    header(draw, "5", ["如果发不出去", "用浏览器打开链接"])
    sx, sy, sw, sh = phone_screen(draw, WHITE)
    draw.rounded_rectangle((sx + 16, sy + 24, sx + sw - 16, sy + 100), radius=16, fill=GOLD)
    draw.text((sx + 32, sy + 44), "长按这里粘贴链接", font=font(28), fill=INK)
    label_button(draw, (sx + 28, sy + 180, sw - 56, 90), "下载", GREEN, WHITE, mark=True)
    footer(draw)
    save(image, "guide/browser.png")


def main() -> None:
    flow_share()
    flow_copy()
    flow_paste()
    guide_step1()
    guide_step2()
    guide_step3()
    guide_android4()
    guide_ios4()
    guide_browser()
    print("wrote pictures to", ROOT)


if __name__ == "__main__":
    main()
