import psycopg2
from psycopg2 import sql
import requests
import json

def convert_timestamp(milliseconds):
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.fromtimestamp(milliseconds / 1000, tz=ist).strftime('%Y-%m-%d %H:%M:%S')

def fetch_and_insert_bus_data(from_city, to_city, trip_date):
    # Fetch data from the Zingbus API
    url = f"https://www.zingbus.com/v1/search/zingbus/buses/?fromCity={from_city}&toCity={to_city}&tripDate={trip_date}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            print(f"Response content: {response.text}")
            return

        raw_content = response.text
        json_objects = raw_content.split('\n')  # Assuming JSON objects are separated by newlines
        bus_data = [json.loads(obj) for obj in json_objects if obj.strip()]
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the request: {e}")
        return

    # Insert fetched data into the PostgreSQL database
    conn = psycopg2.connect(
        dbname="BUS_DATA",  # Change this to your database name
        user="postgres",  # Replace with your PostgreSQL username
        password="2301",  # Replace with your PostgreSQL password
        host="192.168.42.113",  # Or your host (use 'localhost' if running locally)
        port="5432"  # Default port for PostgreSQL
    )

    # Create a cursor object to interact with the database
    cur = conn.cursor()

    # Create the table if it doesn't exist
    create_table_query = """
        CREATE TABLE IF NOT EXISTS buses (
            id SERIAL PRIMARY KEY,
            source_city VARCHAR(255) NOT NULL,
            destination_city VARCHAR(255) NOT NULL,
            bus_type VARCHAR(255),
            departure_time TIMESTAMP NOT NULL,
            arrival_time TIMESTAMP NOT NULL,
            total_travel_time VARCHAR(255),
            fare NUMERIC
        )
    """
    cur.execute(create_table_query)

    # Loop through the list of JSON objects
    for data in bus_data:  # bus_data is a list of dictionaries
        trips = data.get("trips", [])
        for trip in trips:
            source_city = trip.get("fromCity", "")
            destination_city = trip.get("toCity", "")
            departure_time_ist = convert_timestamp(trip.get("startTimeInMills", 0))
            arrival_time_ist = convert_timestamp(trip.get("endTimeInMills", 0))

            bus_info = {
                "source_city": source_city,
                "destination_city": destination_city,
                "bus_type": trip.get("type", ""),
                "departure_time": departure_time_ist,
                "arrival_time": arrival_time_ist,
                "total_travel_time": trip.get("timeDifference", ""),
                "fare": trip.get("fare", ""),
            }

            # Prepare the SQL INSERT statement
            insert_query = """
                INSERT INTO buses (source_city, destination_city, bus_type, departure_time, arrival_time, total_travel_time, fare)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(insert_query, (
                bus_info['source_city'], 
                bus_info['destination_city'], 
                bus_info['bus_type'], 
                bus_info['departure_time'], 
                bus_info['arrival_time'], 
                bus_info['total_travel_time'], 
                bus_info['fare'], 
            ))

    # Commit the transaction
    conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    print("Data fetched and inserted successfully into the PostgreSQL database.")

# # Example usage
# fetch_and_insert_bus_data("Delhi", "Jaipur", "2024-12-01")