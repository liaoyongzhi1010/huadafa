def test_models_define_tables():
    from app.models import Base

    table_names = set(Base.metadata.tables.keys())
    assert "products" in table_names
    assert "batches" in table_names
    assert "anti_codes" in table_names
    assert "scan_events" in table_names
    assert "recommendations" in table_names
    assert "page_contents" in table_names
    assert "verify_configs" in table_names

