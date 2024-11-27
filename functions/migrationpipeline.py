import psycopg2
from pymongo import MongoClient
import json

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

# PostgreSQL setup
def get_postgres_connection():
    try:
        connection = psycopg2.connect(
            host="localhost",
            database="TrainDB",  # Replace with your PostgreSQL database name
            user="postgres",  # Replace with your PostgreSQL username
            password="0000"  # Replace with your PostgreSQL password
        )
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

# Create PostgreSQL table for train data
def create_postgres_table():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS TrainDetails (
        train_number TEXT,
        train_name TEXT,
        source_station_code TEXT,
        source_city TEXT,
        destination_station_code TEXT,
        destination_city TEXT,
        travel_date DATE,
        ticket_prices JSONB
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
    # Get MongoDB data
    collection = get_mongo_connection()
    if collection is None:
        print("Failed to connect to MongoDB. Aborting data transfer.")
        return

    try:
        mongo_data = list(collection.find({}))  # Fetch all records from MongoDB
        if not mongo_data:
            print("No data found in MongoDB to transfer.")
            return

        # Connect to PostgreSQL
        connection = get_postgres_connection()
        if connection is None:
            print("Failed to connect to PostgreSQL. Aborting data transfer.")
            return

        cursor = connection.cursor()

        # Insert data into PostgreSQL
        insert_query = """
        INSERT INTO TrainDetails (
            train_number, train_name, source_station_code, source_city,
            destination_station_code, destination_city, travel_date, ticket_prices
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;  -- Prevent duplicate entries
        """
        for record in mongo_data:
            # Prepare the data
            train_number = record.get("Train Number", "N/A")
            train_name = record.get("Train Name", "N/A")
            source_station_code = record.get("Source Station Code", "N/A")
            source_city = record.get("Source City", "N/A")
            destination_station_code = record.get("Destination Station Code", "N/A")
            destination_city = record.get("Destination City", "N/A")
            travel_date = record.get("Travel Date", None)
            ticket_prices = record.get("Ticket Prices", {})

            # Execute the insert query
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

# Main function to run the pipeline
if __name__ == "__main__":
    create_postgres_table()  # Ensure PostgreSQL table exists
    transfer_data_to_postgres()  # Transfer data from MongoDB to PostgreSQL