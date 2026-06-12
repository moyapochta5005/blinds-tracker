"""Генерация PWA-иконок с буквой «Т» на синем фоне."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Цвета бренда
BACKGROUND_COLOR = "#3366FF"
TEXT_COLOR = "#FFFFFF"

STATIC_DIR = Path(__file__).parent / "static"
SIZES = (192, 512)

# Пути к шрифтам с поддержкой кириллицы (macOS / Linux)
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Подбирает шрифт с кириллицей или возвращает встроенный."""
    for font_path in FONT_CANDIDATES:
        path = Path(font_path)
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    return ImageFont.load_default()


def create_icon(size: int) -> Image.Image:
    """Рисует квадратную иконку заданного размера."""
    image = Image.new("RGB", (size, size), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)

    font_size = int(size * 0.55)
    font = _load_font(font_size)
    text = "Т"

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) / 2 - bbox[0]
    y = (size - text_height) / 2 - bbox[1]

    draw.text((x, y), text, fill=TEXT_COLOR, font=font)
    return image


def main() -> None:
    """Сохраняет icon-192.png и icon-512.png в app/static/."""
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        output_path = STATIC_DIR / f"icon-{size}.png"
        create_icon(size).save(output_path, "PNG")
        print(f"Создан: {output_path}")


if __name__ == "__main__":
    main()
