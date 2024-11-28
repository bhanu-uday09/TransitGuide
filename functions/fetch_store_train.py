import requests
import json
from datetime import datetime
from pymongo import MongoClient
import psycopg2

# MongoDB setup
def get_mongo_connection():
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["TrainDatabase"]  
        collection = db["TrainDetails"]  
        return collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

# Function to get user input and format the date
def get_user_input():
    source = input("Enter source station code: ").strip().upper()
    destination = input("Enter destination station code: ").strip().upper()
    srcCode = source  # Replace with actual station code logic if needed
    destCode = destination
    travel_date = input("Enter travel date (YYYY-MM-DD): ").strip()
    formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y%m%d")
    return srcCode, destCode, formatted_date

# Main function to fetch train details
def fetch_train_details(source, destination, formatted_date):
    url = f"https://railways.makemytrip.com/api/tbsWithAvailabilityAndRecommendation/{source}/{destination}/{formatted_date}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        trains = data.get("trainBtwnStnsList", [])
        if not trains:
            print("No trains found for the given input.")
            return

        extracted_trains = []
        for train in trains:
            ticket_prices = {availability.get("className", "N/A"): availability.get("totalFare", "N/A") for availability in train.get("tbsAvailability", [])}
            train_info = {
                "Train Number": train.get("trainNumber"),
                "Train Name": train.get("trainName"),
                "Source Station Code": train.get("frmStnCode"),
                "Source City": train.get("frmStnCity"),
                "Destination Station Code": train.get("toStnCode"),
                "Destination City": train.get("toStnCity"),
                "Travel Date": formatted_date,
                "Ticket Prices": {class_name: ticket_prices.get(class_name, "Not Available") for class_name in ["SL", "3A", "2A", "1A"]},
            }
            extracted_trains.append(train_info)
        print(json.dumps(extracted_trains, indent=4))
        collection = get_mongo_connection()
        if collection is not None:
            result = collection.insert_many(extracted_trains)
            print(f"Inserted {len(result.inserted_ids)} train records into MongoDB.")
        else:
            print("MongoDB connection failed. Data was not inserted.")
    except requests.exceptions.RequestException as e:
        print(f"HTTP Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

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

# Create PostgreSQL table for train data
def create_postgres_table():
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
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        print("Table TrainDetails created or already exists.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error creating table in PostgreSQL: {e}")

# Transfer data from MongoDB to PostgreSQL
def transfer_data_to_postgres():
    collection = get_mongo_connection()
    if collection is None:
        print("Failed to connect to MongoDB. Aborting data transfer.")
        return
    try:
        mongo_data = list(collection.find({}))
        if not mongo_data:
            print("No data found in MongoDB to transfer.")
            return
        connection = get_postgres_connection()
        if connection is None:
            print("Failed to connect to PostgreSQL. Aborting data transfer.")
            return
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO TrainDetails (
            train_number, train_name, source_station_code, source_city,
            destination_station_code, destination_city, travel_date, ticket_prices
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (train_number, travel_date) DO NOTHING;
        """
        for record in mongo_data:
            train_number = record.get("Train Number", "N/A")
            train_name = record.get("Train Name", "N/A")
            source_station_code = record.get("Source Station Code", "N/A")
            source_city = record.get("Source City", "N/A")
            destination_station_code = record.get("Destination Station Code", "N/A")
            destination_city = record.get("Destination City", "N/A")
            travel_date = record.get("Travel Date", None)
            ticket_prices = record.get("Ticket Prices", {})
            cursor.execute(
                insert_query,
                (
                    train_number, train_name, source_station_code, source_city,
                    destination_station_code, destination_city, travel_date, json.dumps(ticket_prices)
                )
            )
        connection.commit()
        print(f"Transferred {len(mongo_data)} records from MongoDB to PostgreSQL.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error transferring data to PostgreSQL: {e}")
