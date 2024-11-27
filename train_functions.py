import requests
import json
from datetime import datetime
import random
import psycopg2
from psycopg2 import sql

# API Configuration
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

# Price mapping for classes with randomization
def get_class_price(class_name):
    """Return a random price for a given class."""
    price_mapping = {
        "2S": random.randint(325, 435),  # Fixed price
        "SL": random.randint(1000, 1200),  # Slight variation around the base price
        "CC": random.randint(1700, 1900),
        "3A": random.randint(2400, 2600),
        "3E": random.randint(2400, 2600),
        "2A": random.randint(3100, 3300),
        "1A": random.randint(3800, 4000)
    }
    return price_mapping.get(class_name, 0)  # Default to 0 if class not found

def fetch_train_data(source, destination):
    """
    Fetch train details from the API based on user-provided source, destination, and date.
    """
    api_url = f"https://railways.makemytrip.com/api/tbsWithAvailabilityAndRecommendation/{source}/{destination}/20241219"
    try:
        response = requests.get(api_url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        trains = data.get("trainBtwnStnsList", [])
        
        # Extract train details
        extracted_trains = []
        for train in trains:
            # Extract available classes
            classes = []
            if "tbsAvailability" in train:
                classes = [availability.get("className", "N/A") for availability in train.get("tbsAvailability", [])]

            # Create a row for each class
            for cls in classes:
                extracted_trains.append({
                    "train_number": train.get("trainNumber"),
                    "train_name": train.get("trainName"),
                    "from_station_code": train.get("frmStnCode"),
                    "from_station_city": train.get("frmStnCity"),
                    "to_station_code": train.get("toStnCode"),
                    "to_station_city": train.get("toStnCity"),
                    "price": get_class_price(cls),  # Assign price based on class
                    "class": cls,  # Class column
                    "date": '20241219'  # User-provided date
                })
        return extracted_trains
    except requests.exceptions.RequestException as e:
        print(f"Error fetching API data: {e}")
        return []

def search_trains():
    """
    Prompt user for source, destination, and date, then fetch and display train details.
    """
    # User input
    source = input("Enter source station code (e.g., NDLS): ").strip().upper()
    destination = input("Enter destination station code (e.g., BCT): ").strip().upper()
    date = input("Enter travel date (YYYY-MM-DD): ").strip()

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format. Please enter the date in YYYY-MM-DD format.")
        return

    # Fetch train data
    train_data = fetch_train_data(source, destination, date)

    # Display results
    if train_data:
        print("\nAvailable Trains:")
        for train in train_data:
            print(f"Train Number: {train['train_number']}, Train Name: {train['train_name']}")
            print(f"From: {train['from_station_city']} ({train['from_station_code']})")
            print(f"To: {train['to_station_city']} ({train['to_station_code']})")
            print(f"Class: {train['class']}, Price: ₹{train['price']}, Date: {train['date']}\n")
    else:
        print("No trains found for the given source, destination, and date.")


# PostgreSQL Configuration
POSTGRES_HOST = "192.168.42.185"
POSTGRES_DB = "Train_Database"
POSTGRES_USER = "postgres"
POSTGRES_PASSWORD = "root"
POSTGRES_TABLE = "train_data" 

def create_postgres_table():
    """
    Create a PostgreSQL table to store train data if it doesn't already exist.
    """
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        cur = conn.cursor()
        create_table_query = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                train_number TEXT,
                train_name TEXT,
                from_station_code TEXT,
                from_station_city TEXT,
                to_station_code TEXT,
                to_station_city TEXT,
                price INTEGER,
                class TEXT,
                date DATE
            )
        """).format(table=sql.Identifier(POSTGRES_TABLE))
        cur.execute(create_table_query)
        conn.commit()
        cur.close()
        conn.close()
        print("Table created or verified successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")

def insert_data_to_postgres(data):
    """
    Insert fetched train data into the PostgreSQL database.
    :param data: List of dictionaries containing train details.
    """
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        cur = conn.cursor()
        insert_query = sql.SQL("""
            INSERT INTO {table} (
                train_number, train_name, from_station_code, 
                from_station_city, to_station_code, to_station_city, price, class, date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """).format(table=sql.Identifier(POSTGRES_TABLE))

        for record in data:
            try:
                cur.execute(insert_query, (
                    record["train_number"],
                    record["train_name"],
                    record["from_station_code"],
                    record["from_station_city"],
                    record["to_station_code"],
                    record["to_station_city"],
                    record["price"],
                    record["class"],
                    record["date"]
                ))
            except Exception as e:
                print(f"Error inserting record: {record} -> {e}")

        conn.commit()
        cur.close()
        conn.close()
        print("Data successfully inserted into the database.")
    except Exception as e:
        print(f"Error connecting to database: {e}")
