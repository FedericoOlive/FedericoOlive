import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "profile-info.md"
IMAGE_FILE = ROOT / "data" / "profile-image.txt"
GAME_SVG_FILE = ROOT / "assets" / "game-animation.svg"
PANEL_SVG_FILE = ROOT / "assets" / "profile-panel.svg"
README_FILE = ROOT / "README.md"

IMAGE_FONT_SIZE = 10
IMAGE_CHAR_WIDTH = 6
IMAGE_LINE_HEIGHT = 10

INFO_FONT_SIZE = 15
INFO_CHAR_WIDTH = 9
INFO_LINE_HEIGHT = 20

PORTRAIT_WIDTH = 250
INFO_WIDTH = 580
PANEL_PADDING = 16
COLUMN_GAP = 12
STACK_GAP = 10

VALUE_COLUMN = 30
PAIR_VALUE_COLUMN = 14

LINE_MARKERS = {
    "Uptime": ["uptime"],
    "Repos": ["repos", "stars"],
    "Commits": ["commits", "followers"],
    "Lines of Code on GitHub": ["loc", "loc_add", "loc_del"],
}
ALL_MARKERS = [marker for group in LINE_MARKERS.values() for marker in group]
MARKER_CLASSES = {"loc_add": "added", "loc_del": "removed"}

PANEL_SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    .portrait text {{ font-family: 'Courier New', Courier, monospace; font-size: {image_font_size}px; fill: #00ff41; white-space: pre; }}
    .info text {{ font-family: 'Courier New', Courier, monospace; font-size: {info_font_size}px; white-space: pre; }}
    .info .header {{ fill: #00ff41; font-weight: bold; }}
    .info .key    {{ fill: #ffa657; }}
    .info .dots   {{ fill: #484f58; }}
    .info .value  {{ fill: #c9d1d9; }}
    .info .added   {{ fill: #3fb950; }}
    .info .removed {{ fill: #f85149; }}
  </style>
  <rect x="0.5" y="0.5" width="{rect_width}" height="{rect_height}" rx="8" fill="#0d1117" stroke="#3d444d"/>
{parts}
</svg>
"""

README_TEMPLATE = """<div align="center">
  <img src="assets/profile-panel.svg" alt="ASCII portrait, profile info and Space Invaders animation" />
</div>
"""


def portrait_part() -> tuple:
    lines = [line.rstrip() for line in IMAGE_FILE.read_text(encoding="utf-8-sig").splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    indent = min(len(line) - len(line.lstrip()) for line in lines if line)
    lines = [line[indent:] for line in lines]
    width = max(len(line) for line in lines) * IMAGE_CHAR_WIDTH
    height = len(lines) * IMAGE_LINE_HEIGHT + IMAGE_FONT_SIZE // 2
    texts = "\n".join(
        f'    <text x="0" y="{IMAGE_FONT_SIZE + index * IMAGE_LINE_HEIGHT}" xml:space="preserve">{html.escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    return texts, width, height


def parse_data():
    for raw_line in DATA_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.rstrip()
        if not line:
            yield ("blank", "")
        elif line.startswith("- "):
            yield ("header", line[2:].strip())
        else:
            yield ("item", line.removeprefix("* ").strip())


def item_parts(content: str) -> list:
    parts = []
    for index, segment in enumerate(content.split(" | ")):
        segment = segment.removeprefix("* ")
        if index:
            parts.append(("dots", " | "))
        column = VALUE_COLUMN if index == 0 else PAIR_VALUE_COLUMN
        key, separator, value = segment.partition(": ")
        if separator:
            dots = "." * max(column - len(key) - 3, 2)
            parts += [("key", key), ("dots", f": {dots} "), ("value", value)]
        else:
            parts.append(("value", segment))
    return parts


def plain_text(parts: list) -> str:
    return "".join(text for _, text in parts).replace("{auto}", "--")


def render_parts(parts: list, markers: list) -> str:
    pending = iter(markers)
    tspans = []
    for css_class, text in parts:
        escaped = html.escape(text)
        for segment in re.split(r"(\{auto\}(?:\+\+|--)?)", escaped):
            if not segment:
                continue
            if segment.startswith("{auto}"):
                marker = next(pending)
                suffix = segment.removeprefix("{auto}")
                value = f"<!--{marker}-->--<!--/{marker}-->{suffix}"
                tspans.append(f'<tspan class="{MARKER_CLASSES.get(marker, css_class)}">{value}</tspan>')
            else:
                tspans.append(f'<tspan class="{css_class}">{segment}</tspan>')
    return "".join(tspans)


def info_part() -> tuple:
    entries = list(parse_data())
    while entries and entries[-1][0] == "blank":
        entries.pop()

    parsed_items = [item_parts(content) for kind, content in entries if kind == "item"]
    line_width = max(len(plain_text(parts)) for parts in parsed_items)

    texts = []
    y = INFO_FONT_SIZE
    for kind, content in entries:
        if kind == "header":
            title = f"{content} " + "─" * max(line_width - len(content) - 1, 3)
            texts.append(f'    <text x="0" y="{y}" xml:space="preserve" class="header">{html.escape(title)}</text>')
        elif kind == "item":
            key = content.removeprefix("* ").partition(":")[0].strip()
            body = render_parts(item_parts(content), LINE_MARKERS.get(key, []))
            texts.append(f'    <text x="0" y="{y}" xml:space="preserve">{body}</text>')
        y += INFO_LINE_HEIGHT

    width = line_width * INFO_CHAR_WIDTH + 8
    height = y - INFO_LINE_HEIGHT + INFO_FONT_SIZE // 2
    return "\n".join(texts), width, height


def game_part() -> tuple:
    content = GAME_SVG_FILE.read_text(encoding="utf-8")
    width, height = (int(value) for value in re.search(r'viewBox="0 0 (\d+) (\d+)"', content).groups())
    inner = content[content.index(">", content.index("<svg")) + 1 : content.rindex("</svg>")]
    return inner, width, height


def nested_svg(name: str, x: float, y: float, width: float, height: float, native_width: int, native_height: int, inner: str) -> str:
    return (
        f'  <svg class="{name}" x="{x}" y="{y:.1f}" width="{width}" height="{height:.1f}" '
        f'viewBox="0 0 {native_width} {native_height}">\n{inner}\n  </svg>'
    )


def build_panel() -> None:
    portrait_inner, portrait_native_w, portrait_native_h = portrait_part()
    info_inner, info_native_w, info_native_h = info_part()
    game_inner, game_native_w, game_native_h = game_part()

    portrait_height = portrait_native_h * PORTRAIT_WIDTH / portrait_native_w
    game_height = game_native_h * PORTRAIT_WIDTH / game_native_w
    left_height = portrait_height + STACK_GAP + game_height
    info_height = info_native_h * INFO_WIDTH / info_native_w
    content_height = max(left_height, info_height)

    panel_width = PANEL_PADDING + PORTRAIT_WIDTH + COLUMN_GAP + INFO_WIDTH + PANEL_PADDING
    panel_height = round(content_height) + 2 * PANEL_PADDING

    left_top = PANEL_PADDING + (content_height - left_height) / 2
    info_top = PANEL_PADDING + (content_height - info_height) / 2
    info_x = PANEL_PADDING + PORTRAIT_WIDTH + COLUMN_GAP

    fragments = [
        nested_svg("portrait", PANEL_PADDING, left_top, PORTRAIT_WIDTH, portrait_height,
                   portrait_native_w, portrait_native_h, portrait_inner),
        nested_svg("game", PANEL_PADDING, left_top + portrait_height + STACK_GAP, PORTRAIT_WIDTH, game_height,
                   game_native_w, game_native_h, game_inner),
        nested_svg("info", info_x, info_top, INFO_WIDTH, info_height,
                   info_native_w, info_native_h, info_inner),
    ]

    svg = PANEL_SVG_TEMPLATE.format(
        width=panel_width,
        height=panel_height,
        rect_width=panel_width - 1,
        rect_height=panel_height - 1,
        image_font_size=IMAGE_FONT_SIZE,
        info_font_size=INFO_FONT_SIZE,
        parts="\n".join(fragments),
    )
    PANEL_SVG_FILE.write_text(preserve_stats(svg), encoding="utf-8")


def preserve_stats(content: str) -> str:
    if not PANEL_SVG_FILE.exists():
        return content
    previous = PANEL_SVG_FILE.read_text(encoding="utf-8")
    for marker in ALL_MARKERS:
        match = re.search(f"<!--{marker}-->(.*?)<!--/{marker}-->", previous, re.DOTALL)
        if match and match.group(1) != "--":
            content = re.sub(
                f"(<!--{marker}-->)(.*?)(<!--/{marker}-->)",
                lambda m, value=match.group(1): f"{m.group(1)}{value}{m.group(3)}",
                content,
                flags=re.DOTALL,
            )
    return content


def main() -> None:
    build_panel()
    README_FILE.write_text(README_TEMPLATE, encoding="utf-8")


if __name__ == "__main__":
    main()
