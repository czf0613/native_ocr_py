import pathlib
import pytest

SAMPLE_DIR = pathlib.Path(__file__).parent


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
