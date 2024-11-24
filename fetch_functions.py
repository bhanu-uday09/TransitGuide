import http.client
import json
from datetime import datetime
from config import get_indigo_db_connection, get_airindia_db_connection, get_spicejet_db_connection
import pandas as pd

# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code'])

def get_airport_code(city):
    try:
        # Filter the DataFrame to find the airport code for the given city
        result = airport_df[airport_df['city'].str.lower() == city.lower()]['airport_code']
        return result.iloc[0] if not result.empty else None
    except Exception as e:
        print(f"Error fetching airport code for {city}: {e}")
        return None

def make_api_request(endpoint):
    conn = http.client.HTTPSConnection("tripadvisor16.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': "50689ccaf0msh3ccdffedc7edf0ep166af2jsnc2535a7c72bf",
        'x-rapidapi-host': "tripadvisor16.p.rapidapi.com"
    }

    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    if res.status != 200:
        raise Exception(f"API call failed with status {res.status}")
    data = res.read()
    return json.loads(data.decode("utf-8"))

def ensure_table_exists(conn_func, table_name, create_table_query):
    """Ensure the table exists in the database."""
    try:
        conn = conn_func()
        cur = conn.cursor()
        cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", (table_name.lower(),))
        if not cur.fetchone()[0]:
            print(f"Creating table {table_name}...")
            cur.execute(create_table_query)
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error ensuring table {table_name} exists: {str(e)}")

def fetch_flight_data(api_endpoint):
    """Fetch flight data from the API."""
    response = make_api_request(api_endpoint)
    return response.get("data", {}).get("flights", [])

def insert_flight_data(conn_func, insert_query, flights, parse_function):
    """Insert flight data into the database."""
    if not flights:
        print("No flights found.")
        return

    try:
        conn = conn_func()
        cur = conn.cursor()

        for flight in flights:
            for segment in flight["segments"]:
                for leg in segment["legs"]:
                    values = parse_function(flight, leg)
                    if values:
                        # Debug: Print values to verify structure
                        print(f"Inserting values: {values}")
                        cur.execute(insert_query, values)

        conn.commit()
        cur.close()
        conn.close()
        print("Data inserted successfully.")
    except Exception as e:
        print(f"Error inserting data: {str(e)}")

# IndiGo Airline Functions
def handle_indigo_flights(source_code, destination_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_code}"
        f"&destinationAirportCode={destination_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=6E"
    )
    table_name = "IndigoFlights"
    create_table_query = """
        CREATE TABLE IF NOT EXISTS IndigoFlights (
            id SERIAL PRIMARY KEY,
            source VARCHAR(10),
            destination VARCHAR(10),
            flight_number VARCHAR(10),
            departure_date TIMESTAMP,
            arrival_time TIMESTAMP,
            fare DECIMAL,
            class VARCHAR(20)
        );
    """
    insert_query = """
        INSERT INTO IndigoFlights (
            source, destination, flight_number, 
            departure_date, arrival_time, fare, 
            class
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    def parse_indigo_flight(flight, leg):
        return (
            leg.get("originStationCode", ""),
            leg.get("destinationStationCode", ""),
            leg.get("flightNumber", ""),
            datetime.fromisoformat(leg.get("departureDateTime", datetime.now().isoformat())),
            datetime.fromisoformat(leg.get("arrivalDateTime", datetime.now().isoformat())),
            flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
            leg.get("classOfService", "ECONOMY")
        )

    ensure_table_exists(get_indigo_db_connection, table_name, create_table_query)
    flights = fetch_flight_data(api_endpoint)
    insert_flight_data(get_indigo_db_connection, insert_query, flights, parse_indigo_flight)

# SpiceJet Airline Functions
def handle_spicejet_flights(source_code, destination_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_code}"
        f"&destinationAirportCode={destination_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=SG"
    )
    table_name = "SpiceJetFlights"
    create_table_query = """
        CREATE TABLE IF NOT EXISTS SpiceJetFlights (
            id SERIAL PRIMARY KEY,
            source_city VARCHAR(10),
            destination_city VARCHAR(10),
            flight_number VARCHAR(10),
            departure_date TIMESTAMP,
            arrival_time TIMESTAMP,
            fare DECIMAL,
            class VARCHAR(20)
        );
    """
    insert_query = """
        INSERT INTO SpiceJetFlights (
            source_city, destination_city, flight_number, 
            departure_date, arrival_time, fare, class
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    def parse_spicejet_flight(flight, leg):
        return (
            leg.get("originStationCode", ""),
            leg.get("destinationStationCode", ""),
            leg.get("flightNumber", ""),
            datetime.fromisoformat(leg.get("departureDateTime", datetime.now().isoformat())),
            datetime.fromisoformat(leg.get("arrivalDateTime", datetime.now().isoformat())),
            flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
            leg.get("classOfService", "ECONOMY")
        )

    ensure_table_exists(get_spicejet_db_connection, table_name, create_table_query)
    flights = fetch_flight_data(api_endpoint)
    insert_flight_data(get_spicejet_db_connection, insert_query, flights, parse_spicejet_flight)

# AirIndia Airline Functions
def handle_air_india_flights(source_code, destination_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_code}"
        f"&destinationAirportCode={destination_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=AI"
    )
    table_name = "AirIndiaFlights"
    create_table_query = """
        CREATE TABLE IF NOT EXISTS AirIndiaFlights (
            id SERIAL PRIMARY KEY,
            origin_airport VARCHAR(10),
            destination_airport VARCHAR(10),
            flight_no VARCHAR(10),
            departure_timestamp TIMESTAMP,
            arrival_timestamp TIMESTAMP,
            fare DECIMAL,
            travel_class VARCHAR(20)
        );
    """
    insert_query = """
        INSERT INTO AirIndiaFlights (
            origin_airport, destination_airport, flight_no, 
            departure_timestamp, arrival_timestamp, fare, 
            travel_class
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    def parse_air_india_flight(flight, leg):
        return (
            leg.get("originStationCode", ""),
            leg.get("destinationStationCode", ""),
            leg.get("flightNumber", ""),
            datetime.fromisoformat(leg.get("departureDateTime", datetime.now().isoformat())),
            datetime.fromisoformat(leg.get("arrivalDateTime", datetime.now().isoformat())),
            flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
            leg.get("classOfService", "ECONOMY")
        )

    ensure_table_exists(get_airindia_db_connection, table_name, create_table_query)
    flights = fetch_flight_data(api_endpoint)
    insert_flight_data(get_airindia_db_connection, insert_query, flights, parse_air_india_flight)
    
