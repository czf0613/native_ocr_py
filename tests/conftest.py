import pathlib
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
SAMPLE_IMAGE = FIXTURES_DIR / "sample.png"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sample-image",
        default=str(SAMPLE_IMAGE),
        help="Path to the sample image used by OCR tests",
    )


@pytest.fixture(scope="session")
def sample_image_path(request: pytest.FixtureRequest) -> pathlib.Path:
    path = pathlib.Path(request.config.getoption("--sample-image"))
    if not path.exists():
        pytest.skip(f"Sample image not found: {path}")
    return path


@pytest.fixture(scope="session")
def sample_image_bytes(sample_image_path: pathlib.Path) -> bytes:
    return sample_image_path.read_bytes()
