import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
from config import get_indigo_db_connection, get_airindia_db_connection, get_spicejet_db_connection, get_globalview_db_connection
import psycopg2
import pandas as pd

# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code','railway_station_code'])

def get_closest_city(user_city):
    """
    Find the closest matching city to the user's input using fuzzy matching.
    """
    try:
        # List of available city names
        city_list = airport_df['city'].tolist()

        # Perform fuzzy matching
        closest_match, score, _ = process.extractOne(
            user_city.strip().title(), city_list, scorer=fuzz.ratio
        )

        # Debugging: Print matching details
        print(f"Input: {user_city}, Closest Match: {closest_match}, Score: {score}")

        # Threshold to ensure it's a valid match
        if score >= 50:  # 70 is a lenient similarity threshold
            return closest_match
        else:
            return None
    except Exception as e:
        print(f"Error finding closest city: {e}")
        return None


# get_closest_city('Hydrabad')


def get_airport_code(user_city):
    """
    Get the airport code for the given city.
    """
    try:
        # Find the closest matching city
        closest_city = get_closest_city(user_city)

        if closest_city:
            # Filter the DataFrame to find the airport code for the closest city
            result = airport_df[airport_df['city'] == closest_city]['airport_code']
            return result.iloc[0] if not result.empty else None
        else:
            return None
    except Exception as e:
        print(f"Error fetching airport code for {user_city}: {e}")
        return None
    
    
# get_airport_code("Bumbai")

def get_railway_station_code(user_city):
    """
    Get the airport code for the given city.
    """
    try:
        # Find the closest matching city
        closest_city = get_closest_city(user_city)

        if closest_city:
            # Filter the DataFrame to find the airport code for the closest city
            result = airport_df[airport_df['city'] == closest_city]['railway_station_code']
            return result.iloc[0] if not result.empty else None
        else:
            return None
    except Exception as e:
        print(f"Error fetching airport code for {user_city}: {e}")
        return None
    
    
# get_railway_station_code("Bumbai")