# seed_db.py
import pandas as pd
from sqlalchemy import create_engine

# Your exact Neon connection string
NEON_URL = "postgresql://neondb_owner:npg_g8W3quisGALk@ep-icy-heart-ahs1nd55.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(NEON_URL)

try:
    # 1. Load the extracted CSVs
    print("Reading CSV files...")
    movies = pd.read_csv('movies.csv')
    ratings = pd.read_csv('ratings.csv')

    # 2. Clean up column names for Postgres compliance
    movies = movies.rename(columns={'movieId': 'movie_id'})
    ratings = ratings.rename(columns={'userId': 'username', 'movieId': 'movie_id'})

    # Convert generic user IDs to string usernames (e.g., user_1, user_2)
    ratings['username'] = 'user_' + ratings['username'].astype(str)

    # 3. Push directly into your Neon Postgres instance
    print("Uploading movies to Neon (this takes a few seconds)...")
    movies.to_sql('movies', engine, if_exists='replace', index=False)

    print("Uploading 100k ratings to Neon...")
    ratings.to_sql('ratings', engine, if_exists='replace', index=False)

    print("🚀 Neon Database seeded successfully!")

except FileNotFoundError:
    print("❌ Error: Could not find movies.csv or ratings.csv in this directory.")
except Exception as e:
    print(f"❌ An error occurred: {e}")