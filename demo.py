import requests
import psycopg2
from psycopg2 import sql
from datetime import datetime

# Database connection details
DB_CONFIG = {
    "dbname": "train",
    "user": "postgres",
    "password": "0000",
    "host": "localhost",
    "port": "5432"
}

# API URL
API_URL = "https://railways.makemytrip.com/api/tbsWithAvailabilityAndRecommendation/NDLS/LTT/20241214"

# Database table schema
CREATE_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS train_schedule (
    pid SERIAL PRIMARY KEY,
    train_number VARCHAR(10) NOT NULL,
    train_name VARCHAR(255),
    source_city VARCHAR(255),
    destination_city VARCHAR(255),
    source_station_code VARCHAR(10),
    destination_station_code VARCHAR(10),
    departure_time TIMESTAMP,
    arrival_time TIMESTAMP,
    fare_1a NUMERIC,
    fare_2a NUMERIC,
    fare_3a NUMERIC,
    fare_3e NUMERIC,
    fare_sl NUMERIC
);
"""

# Function to connect to the database
def connect_db():
    return psycopg2.connect(**DB_CONFIG)

# Function to scrape data from the URL
def scrape_data():
    response = requests.get(API_URL)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()

# Function to parse the scraped data
def parse_data(data):
    train_data_list = []
    for train in data:
        fares = {fare["className"]: fare["totalFare"] for fare in train["tbsAvailability"]}

        train_data = {
            "train_number": train["trainNumber"],
            "train_name": train["trainName"],
            "source_city": train["frmStnCity"],
            "destination_city": train["toStnCity"],
            "source_station_code": train["frmStnCode"],
            "destination_station_code": train["toStnCode"],
            "departure_time": datetime.fromtimestamp(train["departureTimeEpochInSec"]),
            "arrival_time": datetime.fromtimestamp(train["arrivalTimeEpochInSec"]),
            "fare_1a": fares.get("1A"),
            "fare_2a": fares.get("2A"),
            "fare_3a": fares.get("3A"),
            "fare_3e": fares.get("3E"),
            "fare_sl": fares.get("SL")
        }
        train_data_list.append(train_data)
    return train_data_list

# Function to insert data into the database
def insert_data(conn, train_data):
    with conn.cursor() as cursor:
        insert_query = """
        INSERT INTO train_schedule (
            train_number,
            train_name,
            source_city,
            destination_city,
            source_station_code,
            destination_station_code,
            departure_time,
            arrival_time,
            fare_1a,
            fare_2a,
            fare_3a,
            fare_3e,
            fare_sl
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        for train in train_data:
            cursor.execute(insert_query, (
                train["train_number"],
                train["train_name"],
                train["source_city"],
                train["destination_city"],
                train["source_station_code"],
                train["destination_station_code"],
                train["departure_time"],
                train["arrival_time"],
                train["fare_1a"],
                train["fare_2a"],
                train["fare_3a"],
                train["fare_3e"],
                train["fare_sl"]
            ))
    conn.commit()

# Main function
def main():
    # Step 1: Connect to the database and create the table
    conn = connect_db()
    with conn.cursor() as cursor:
        cursor.execute(CREATE_TABLE_QUERY)
    conn.commit()

    # Step 2: Scrape data from the API
    raw_data = scrape_data()

    # Step 3: Parse the scraped data
    train_data_list = parse_data(raw_data)

    # Step 4: Insert the parsed data into the database
    insert_data(conn, train_data_list)

    # Close the database connection
    conn.close()
    print("Data scraped and stored successfully!")

if __name__ == "__main__":
    main()