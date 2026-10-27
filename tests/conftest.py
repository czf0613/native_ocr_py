import pathlib
import pytest

SAMPLE_DIR = pathlib.Path(__file__).parent


@pytest.fixture(scope="session", autouse=True)
def current_worktree_extension():
    # A missing/stale extension must fail acceptance, never skip the OCR suite.
    from native_ocr import _ocr_native

    extension_path = pathlib.Path(_ocr_native.__file__).resolve()
    assert extension_path.parent == SAMPLE_DIR.parent / "src" / "native_ocr", extension_path
    assert extension_path.suffix == ".so", extension_path


@pytest.fixture(scope="session")
def text_fixture(tmp_path_factory):
    return _make_text_fixture(
        tmp_path_factory, "vision-text", "/System/Library/Fonts/Helvetica.ttc", 64,
        [("NATIVE OCR 4826", (100, 130)), ("LOWER PANEL 7319", (100, 550))],
    )


@pytest.fixture(scope="session")
def chinese_text_fixture(tmp_path_factory):
    from native_ocr import get_supported_languages

    assert "zh-Hans" in get_supported_languages(), "Simplified Chinese support unavailable"
    return _make_text_fixture(
        tmp_path_factory, "vision-chinese", "/System/Library/Fonts/STHeiti Medium.ttc", 74,
        [("恭喜获得", (100, 130)), ("下方区域 7319", (100, 550))],
    )


def _make_text_fixture(tmp_path_factory, name, font_name, font_size, lines):
    import hashlib
    import json

    pytest.importorskip("PIL", reason="Pillow is required to generate text fixtures")
    from PIL import Image, ImageDraw, ImageFont

    directory = tmp_path_factory.mktemp(name)
    font_path = pathlib.Path(font_name)
    assert font_path.is_file(), f"Required fixture font unavailable: {font_path}"
    font = ImageFont.truetype(str(font_path), font_size)
    image = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(image)
    for text, xy in lines:
        draw.text(xy, text, font=font, fill="black")
    path = directory / "text.png"
    image.save(path)
    metadata = dict(text=lines, font=str(font_path), font_size=font_size,
                    size=image.size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (directory / "fixture.json").write_text(json.dumps(metadata, indent=2))
    print(f"Generated fixture: {metadata}")
    return path


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sample-image",
        default=str(SAMPLE_DIR / "sample.png"),
        help="Path to a sample image for OCR tests",
    )


@pytest.fixture
def sample_image_path(request: pytest.FixtureRequest) -> pathlib.Path:
    return pathlib.Path(request.config.getoption("--sample-image"))


@pytest.fixture
def sample_image_bytes(sample_image_path: pathlib.Path) -> bytes:
    return sample_image_path.read_bytes()
