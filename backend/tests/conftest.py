import pytest

from app.config import Settings
from app.db import Database
from app.seed import seed_catalog


@pytest.fixture(scope="session")
def seeded_db_path(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("db") / "seed.db")
    seed_catalog(Database(path))
    return path


@pytest.fixture()
def db(tmp_path, seeded_db_path):
    """Bản sao DB đã seed, mỗi test một bản để test ghi dữ liệu không ảnh hưởng nhau."""
    import shutil

    path = str(tmp_path / "t.db")
    shutil.copy(seeded_db_path, path)
    return Database(path)


@pytest.fixture()
def settings(tmp_path, seeded_db_path):
    import shutil

    path = str(tmp_path / "app.db")
    shutil.copy(seeded_db_path, path)
    return Settings(db_path=path, frontend_dir=str(tmp_path / "none"), llm_api_key="test-key")
