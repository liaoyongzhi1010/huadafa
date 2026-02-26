def test_can_connect():
    from app.db import engine

    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")

