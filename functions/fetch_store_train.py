import requests
import json
from datetime import datetime
import psycopg2

# PostgreSQL setup
def get_postgres_connection():
    try:
        connection = psycopg2.connect(
            host="localhost",
            database="TrainDB",
            user="postgres",
            password="0000"
        )
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


# Function to create table if it doesn't exist
def create_train_table():
    """
    Create the TrainDetails table in PostgreSQL if it doesn't exist.
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS TrainDetails (
        train_number TEXT NOT NULL,
        train_name TEXT,
        source_station_code TEXT NOT NULL,
        source_city TEXT,
        destination_station_code TEXT NOT NULL,
        destination_city TEXT,
        travel_date DATE NOT NULL,
        ticket_prices JSONB,
        PRIMARY KEY (train_number, travel_date)
    );
    """
    try:
        connection = get_postgres_connection()
        if connection is None:
            return
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
        print("TrainDetails table created or already exists.")
    except Exception as e:
        print(f"Error creating TrainDetails table: {e}")

# Function to fetch train details and store them in PostgreSQL
def fetch_train_details(source, destination, travel_date):
    """
    Fetch train details from the API and store them in the PostgreSQL database.
    """
    formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y%m%d")
    url = f"https://railways.makemytrip.com/api/tbsWithAvailabilityAndRecommendation/{source}/{destination}/{formatted_date}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        # Fetch data from the API
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Extract train details
        trains = data.get("trainBtwnStnsList", [])
        if not trains:
            print("No train details found.")
            return

        # Create a list of train records
        train_records = []
        for train in trains:
            ticket_prices = {availability.get("className", "N/A"): availability.get("totalFare", "N/A") for availability in train.get("tbsAvailability", [])}
            train_record = {
                "train_number": train.get("trainNumber"),
                "train_name": train.get("trainName"),
                "source_station_code": train.get("frmStnCode"),
                "source_city": train.get("frmStnCity"),
                "destination_station_code": train.get("toStnCode"),
                "destination_city": train.get("toStnCity"),
                "travel_date": travel_date,
                "ticket_prices": json.dumps({class_name: ticket_prices.get(class_name, "Not Available") for class_name in ["SL", "3A", "2A", "1A"]})
            }
            train_records.append(train_record)

        # Insert train records into PostgreSQL
        insert_train_data(train_records)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching train details from API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Function to insert train data into PostgreSQL
def insert_train_data(train_records):
    """
    Insert train data into PostgreSQL database.
    """
    insert_query = """
    INSERT INTO TrainDetails (
        train_number, train_name, source_station_code, source_city,
        destination_station_code, destination_city, travel_date, ticket_prices
    ) VALUES (
        %(train_number)s, %(train_name)s, %(source_station_code)s, %(source_city)s,
        %(destination_station_code)s, %(destination_city)s, %(travel_date)s, %(ticket_prices)s
    )
    ON CONFLICT (train_number, travel_date) DO NOTHING;
    """
    try:
        connection = get_postgres_connection()
        if connection is None:
            return
        with connection:
            with connection.cursor() as cursor:
                cursor.executemany(insert_query, train_records)
        print(f"Inserted {len(train_records)} records into TrainDetails table.")
    except Exception as e:
        print(f"Error inserting train records: {e}")



