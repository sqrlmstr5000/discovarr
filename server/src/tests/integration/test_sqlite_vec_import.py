import os
import pytest
import logging
from pathlib import Path

# Assuming 'server/src' is in PYTHONPATH or tests are run such that 'src' is discoverable
from services.database import Database, database as db_proxy
from services.models import Media, MediaResearch
from services.research import ResearchService

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provides a temporary database path for SQLite."""
    db_file = tmp_path / "test_discovarr_integration.db"
    yield db_file
    # Cleanup the db file after test if it exists
    if db_file.exists():
        db_file.unlink()

def test_sqlite_vec_loads_successfully_and_media_detail_table_created(temp_db_path: Path, caplog):
    """
    Tests that sqlite_vec is loaded for SQLite and MediaResearch table is created.
    """
    # Ensure any previous db instance is cleared from proxy and closed
    if db_proxy.obj is not None: # obj is the underlying database connection
        if not db_proxy.is_closed():
            db_proxy.close()
        db_proxy.initialize(None) # Reset the proxy

    original_env_value = os.environ.get("DISCOVARR_TEST_DATABASE")
    os.environ["DISCOVARR_TEST_DATABASE"] = "sqlite"

    caplog.set_level(logging.INFO)

    # Initialize the Database service, which should load sqlite_vec
    db_service = Database(db_path=str(temp_db_path))

    # Check logs for successful loading
    assert "Successfully loaded sqlite_vec extension for SQLite." in caplog.text, \
        "Log message for successful sqlite_vec load not found."

    # Check if MediaResearch table was created (db_proxy is initialized by Database service)
    tables = db_proxy.get_tables()
    assert MediaResearch._meta.table_name in tables, \
        f"{MediaResearch._meta.table_name} table not found. Tables: {tables}"

    # Cleanup
    if original_env_value is None:
        del os.environ["DISCOVARR_TEST_DATABASE"]
    else:
        os.environ["DISCOVARR_TEST_DATABASE"] = original_env_value
    
    db_service.cleanup() # Closes the connection handled by db_service

def test_create_embedding_and_insert_into_media_detail(temp_db_path: Path, caplog):
    """
    Tests creating an embedding with ResearchService and inserting it into MediaResearch.
    """
    # Ensure any previous db instance is cleared from proxy and closed
    if db_proxy.obj is not None:
        if not db_proxy.is_closed():
            db_proxy.close()
        db_proxy.initialize(None)

    original_env_value = os.environ.get("DISCOVARR_TEST_DATABASE")
    os.environ["DISCOVARR_TEST_DATABASE"] = "sqlite"

    caplog.set_level(logging.INFO)

    db_service = Database(db_path=str(temp_db_path))
    research_service = ResearchService() # Uses default model

    assert research_service.model is not None, "SentenceTransformer model failed to load."

    # 1. Create a dummy Media record
    sample_media_data = {
        "tmdb_id": "12345",
        "title": "Test Movie for Embedding",
        "media_type": "movie",
        "source": "tmdb"
    }
    media_id = db_service.create_media(sample_media_data)
    assert media_id is not None, "Failed to create dummy Media record."

    # 2. Create embedding
    sample_text = "This is a test plot summary for a fantastic movie."
    embedding = research_service.get_research_embedding(sample_text)
    assert embedding is not None, "Failed to create embedding."
    assert isinstance(embedding, list)
    assert len(embedding) > 0 # Ensure embedding is not empty

    # 3. Insert into MediaResearch
    media_detail_entry = MediaResearch.create(
        media_id=media_id,
        research=sample_text,
        embedding=embedding # Peewee with sqlite_vec should handle list-to-vector conversion
    )
    assert media_detail_entry.id is not None, "Failed to insert into MediaResearch."

    # 4. Verification (Optional: retrieve and check)
    retrieved_detail = MediaResearch.get_by_id(media_detail_entry.id)
    assert retrieved_detail.research == sample_text
    # Note: Direct comparison of float lists (embeddings) can be tricky due to precision.
    # For simplicity, we'll trust the insertion if no error occurs and text matches.
    # A more robust check would compare embedding similarity or element-wise with tolerance.
    assert len(retrieved_detail.embedding) == len(embedding), "Embedding length mismatch."

    # Cleanup
    if original_env_value is None:
        del os.environ["DISCOVARR_TEST_DATABASE"]
    else:
        os.environ["DISCOVARR_TEST_DATABASE"] = original_env_value
    db_service.cleanup()