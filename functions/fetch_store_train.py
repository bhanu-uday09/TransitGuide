import requests
import json
from datetime import datetime
import psycopg2

# PostgreSQL setup
def get_postgres_connection():
    try:
        connection = psycopg2.connect(
            host="192.168.42.185",
            database="TrainDB",
            user="postgres",
            password="root",
            port="5432"
        )
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def create_train_table():
    """
    Create the TrainDetails table in PostgreSQL with fields for departure, arrival, duration, and fares.
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS TrainDetails (
        train_number TEXT NOT NULL,
        train_name TEXT,
        source_station_code TEXT NOT NULL,
        source_city TEXT,
        destination_station_code TEXT NOT NULL,
        destination_city TEXT,
        departure_date DATE NOT NULL,
        departure_time TIME NOT NULL,
        departure_day TEXT NOT NULL,
        arrival_date DATE NOT NULL,
        arrival_time TIME NOT NULL,
        arrival_day TEXT NOT NULL,
        travel_duration TEXT NOT NULL,
        ticket_prices JSONB,
        PRIMARY KEY (train_number, departure_date)
    );
    """
    try:
        connection = get_postgres_connection()
        if connection is None:
            return
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
        print("TrainDetails table created or already exists with updated schema.")
    except Exception as e:
        print(f"Error creating TrainDetails table: {e}")
                

def fetch_train_details(source, destination, travel_date):
    """
    Fetch train details from the API, process the response, and store in the PostgreSQL database.
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

        # Prepare records for insertion
        train_records = []
        for train in trains:
            departure_time = datetime.strptime(train["departureTime"], "%H:%M")
            arrival_time = datetime.strptime(train["arrivalTime"], "%H:%M")
            travel_duration = f"{train['duration'] // 60}h {train['duration'] % 60}m"
            ticket_prices = {
                availability["className"]: availability["totalFare"]
                for availability in train.get("tbsAvailability", [])
            }

            train_record = {
                "train_number": train["trainNumber"],
                "train_name": train["trainName"],
                "source_station_code": train["frmStnCode"],
                "source_city": train["frmStnCity"],
                "destination_station_code": train["toStnCode"],
                "destination_city": train["toStnCity"],
                "departure_date": travel_date,
                "departure_time": departure_time.time(),
                "departure_day": departure_time.strftime("%A"),
                "arrival_date": travel_date,  # Assuming same-day arrival for simplicity; adjust as needed.
                "arrival_time": arrival_time.time(),
                "arrival_day": arrival_time.strftime("%A"),
                "travel_duration": travel_duration,
                "ticket_prices": json.dumps(ticket_prices),
            }
            train_records.append(train_record)

        # Insert train records into PostgreSQL
        insert_train_data(train_records)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching train details from API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def insert_train_data(train_records):
    """
    Insert train data into PostgreSQL database with updated schema.
    """
    insert_query = """
    INSERT INTO TrainDetails (
        train_number, train_name, source_station_code, source_city,
        destination_station_code, destination_city, departure_date,
        departure_time, departure_day, arrival_date, arrival_time,
        arrival_day, travel_duration, ticket_prices
    ) VALUES (
        %(train_number)s, %(train_name)s, %(source_station_code)s, %(source_city)s,
        %(destination_station_code)s, %(destination_city)s, %(departure_date)s,
        %(departure_time)s, %(departure_day)s, %(arrival_date)s, %(arrival_time)s,
        %(arrival_day)s, %(travel_duration)s, %(ticket_prices)s
    )
    ON CONFLICT (train_number, departure_date) DO NOTHING;
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
             
        
fetch_train_details('VSKP', 'SC', '2024-12-22')
