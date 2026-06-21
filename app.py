import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_sessions'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def get_movie_recommendations(username, top_n=5):
    popular_movies_query = text("""
        SELECT movie_id FROM ratings 
        GROUP BY movie_id 
        HAVING COUNT(rating) >= 15
    """)
    popular_movie_ids = [row[0] for row in db.session.execute(popular_movies_query).fetchall()]
    
    if not popular_movie_ids:
        top_movies_query = text("""
            SELECT m.title FROM movies m 
            JOIN ratings r ON m.movie_id = r.movie_id 
            GROUP BY m.movie_id, m.title 
            ORDER BY COUNT(r.rating) DESC LIMIT :limit
        """)
        return [row[0] for row in db.session.execute(top_movies_query, {'limit': top_n}).fetchall()]

    placeholders = ", ".join(f":id_{i}" for i in range(len(popular_movie_ids)))
    ratings_query = text(f"SELECT username, movie_id, rating FROM ratings WHERE movie_id IN ({placeholders})")
    params = {f"id_{i}": val for i, val in enumerate(popular_movie_ids)}
    
    df_ratings = pd.read_sql_query(ratings_query, db.engine, params=params)
    df_ratings['rating'] = df_ratings['rating'].astype('float32')

    matrix = df_ratings.pivot(index='username', columns='movie_id', values='rating')
    
    if username not in matrix.index:
        top_movies = df_ratings.groupby('movie_id').rating.count().sort_values(ascending=False).head(top_n).index
        placeholders_top = ", ".join(f":tid_{i}" for i in range(len(top_movies)))
        movies_query = text(f"SELECT title FROM movies WHERE movie_id IN ({placeholders_top})")
        t_params = {f"tid_{i}": val for i, val in enumerate(top_movies)}
        return [row[0] for row in db.session.execute(movies_query, t_params).fetchall()]

    matrix_filled = matrix.fillna(0)
    user_sim = cosine_similarity(matrix_filled)
    df_sim = pd.DataFrame(user_sim, index=matrix.index, columns=matrix.index)
    
    sim_scores = df_sim[username].drop(username)
    target_user_ratings = matrix.loc[username]
    unwatched = target_user_ratings[target_user_ratings.isna()].index
    
    predicted_ratings = {}
    for movie in unwatched:
        other_ratings = matrix[movie].drop(username)
        valid_indices = other_ratings.notna()
        if not valid_indices.any():
            continue
        
        weights = sim_scores[valid_indices]
        ratings = other_ratings[valid_indices]
        if weights.sum() > 0:
            predicted_ratings[movie] = np.dot(weights, ratings) / weights.sum()
            
    recommended_movie_ids = [m for m, s in sorted(predicted_ratings.items(), key=lambda x: x[1], reverse=True)[:top_n]]
    
    if recommended_movie_ids:
        placeholders_rec = ", ".join(f":rid_{i}" for i in range(len(recommended_movie_ids)))
        rec_movies_query = text(f"SELECT title FROM movies WHERE movie_id IN ({placeholders_rec})")
        r_params = {f"rid_{i}": val for i, val in enumerate(recommended_movie_ids)}
        return [row[0] for row in db.session.execute(rec_movies_query, r_params).fetchall()]
    return []

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        if username:
            session['username'] = username
            check_sql = text("SELECT COUNT(*) FROM ratings WHERE username = :u")
            count = db.session.execute(check_sql, {'u': username}).scalar()
            if count == 0:
                return redirect(url_for('onboarding'))
            else:
                return redirect(url_for('recommendations'))
    return render_template('login.html')

@app.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    if request.method == 'POST':
        for movie_id, rating in request.form.items():
            if rating:
                insert_sql = text("INSERT INTO ratings (username, movie_id, rating) VALUES (:u, :m, :r)")
                db.session.execute(insert_sql, {'u': username, 'm': int(movie_id), 'r': float(rating)})
        db.session.commit()
        return redirect(url_for('recommendations'))
        
    popular_movies_sql = text("""
        SELECT m.movie_id, m.title FROM movies m 
        JOIN ratings r ON m.movie_id = r.movie_id 
        GROUP BY m.movie_id, m.title 
        ORDER BY COUNT(r.rating) DESC LIMIT 10
    """)
    movies_to_rate = db.session.execute(popular_movies_sql).fetchall()
    return render_template('onboarding.html', movies=movies_to_rate)

@app.route('/recommendations')
def recommendations():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    recs = get_movie_recommendations(username)
    return render_template('recommendations.html', username=username, recommendations=recs)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False)
