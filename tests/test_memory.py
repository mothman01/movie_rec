import pytest
import os
import psutil
from app import app, db, get_movie_recommendations
from sqlalchemy import text

@pytest.fixture
def setup_test_data():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        
        db.session.execute(text("CREATE TABLE IF NOT EXISTS movies (movie_id INTEGER PRIMARY KEY, title TEXT)"))
        db.session.execute(text("CREATE TABLE IF NOT EXISTS ratings (username TEXT, movie_id INTEGER, rating REAL)"))
        
        db.session.execute(text("DELETE FROM ratings"))
        db.session.execute(text("DELETE FROM movies"))
        
        for i in range(1, 20):
            db.session.execute(text("INSERT INTO movies (movie_id, title) VALUES (:i, :t)"), {'i': i, 't': f"Movie {i}"})
            
        for u in range(20):
            for m in range(1, 20):
                db.session.execute(
                    text("INSERT INTO ratings (username, movie_id, rating) VALUES (:u, :m, :r)"),
                    {'u': f"user_{u}", 'm': m, 'r': 4.0}
                )
        db.session.commit()
        yield
        db.session.remove()
        db.drop_all()

def test_recommendation_ram_consumption(setup_test_data):
    process = psutil.Process(os.getpid())
    ram_before = process.memory_info().rss
    
    with app.app_context():
        recommendations = get_movie_recommendations('user_1', top_n=5)
        assert isinstance(recommendations, list)

    ram_after = process.memory_info().rss
    consumed_mb = (ram_after - ram_before) / (1024 * 1024)
    
    assert consumed_mb < 25.0, f"Memory threshold exceeded: {consumed_mb:.2f} MB"

