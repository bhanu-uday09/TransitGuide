import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
from config import get_indigo_db_connection, get_airindia_db_connection, get_spicejet_db_connection, get_globalview_db_connection
import psycopg2
import pandas as pd

# Database connection details
DB_NAME = "TransitGlobal"
DB_USER = "postgres"
DB_PASS = "0000"
DB_HOST = "localhost"
DB_PORT = "5432"

# Function to get database connection
def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code'])

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
    
def fetch_indigo_flights(source_airport_code, destination_airport_code, journey_date):
    conn = http.client.HTTPSConnection("booking-com15.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': "139be57d39msh8396d6c2824a3e8p155bc8jsn25b210898778",
        'x-rapidapi-host': "booking-com15.p.rapidapi.com"
    }

    # API endpoint for Booking.com-IndiGo
    api_endpoint = (
        f"/api/v1/flights/searchFlights?"
        f"fromId={source_airport_code}.AIRPORT&toId={destination_airport_code}.AIRPORT&departDate={journey_date}"
        f"&pageNo=1&adults=1&children=0%2C17&sort=BEST"
        f"&cabinClass=ECONOMY&currency_code=AED"
    )
    
    conn.request("GET", api_endpoint, headers=headers)
    
    res = conn.getresponse()
    if res.status != 200:
        raise Exception(f"API call failed with status {res.status}")
    
    data = res.read()
    flights_data = json.loads(data.decode("utf-8"))
    
    # Parse flight data (adjust fields based on the new response structure)
    flights = flights_data.get("data", {}).get("flights", [])
    if not flights:
        print("No flights found for Indigo.")
        return

    # Ensure database table exists
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
    conn_db = get_indigo_db_connection()
    cur = conn_db.cursor()
    cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", ("indigoflights",))
    if not cur.fetchone()[0]:
        cur.execute(create_table_query)
        conn_db.commit()

    # Insert flight data into the database
    insert_query = """
        INSERT INTO IndigoFlights (
            source, destination, flight_number, 
            departure_date, arrival_time, fare, 
            class
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    for flight in flights:
        for segment in flight["segments"]:
            for leg in segment["legs"]:
                values = (
                    leg.get("originStationCode", ""),
                    leg.get("destinationStationCode", ""),
                    leg.get("flightNumber", ""),
                    datetime.fromisoformat(leg.get("departureDateTime", datetime.now().isoformat())),
                    datetime.fromisoformat(leg.get("arrivalDateTime", datetime.now().isoformat())),
                    flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
                    leg.get("classOfService", "ECONOMY")
                )
                # Debug: Print values to verify structure before inserting
                print(f"Inserting values: {values}")
                cur.execute(insert_query, values)

    conn_db.commit()
    cur.close()
    conn_db.close()
    print("Data inserted successfully into IndigoFlights.")
    
    
def fetch_air_india_flights(source_airport_code, destination_airport_code, journey_date):
    conn = http.client.HTTPSConnection("sky-scanner3.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': "139be57d39msh8396d6c2824a3e8p155bc8jsn25b210898778",
        'x-rapidapi-host': "sky-scanner3.p.rapidapi.com"
    }

    # API endpoint for Sky-Scanner-AirIndia
    api_endpoint = (
        f"/flights/search-one-way?"
        f"fromEntityId={source_airport_code}&toEntityId={destination_airport_code}"
        f"&departDate={journey_date}&cabinClass=economy&airlines=AI"
    )
    
    conn.request("GET", api_endpoint, headers=headers)
    
    res = conn.getresponse()
    if res.status != 200:
        raise Exception(f"API call failed with status {res.status}")
    
    data = res.read()
    flights_data = json.loads(data.decode("utf-8"))
    
    # Parse flight data (adjust fields based on the new response structure)
    flights = flights_data.get("flights", [])
    if not flights:
        print("No flights found for Air India.")
        return

    # Ensure database table exists
    create_table_query = """
        CREATE TABLE IF NOT EXISTS AirIndiaFlights (
            id SERIAL PRIMARY KEY,
            source_airport VARCHAR(10),
            destination_airport VARCHAR(10),
            flight_number VARCHAR(10),
            departure_date TIMESTAMP,
            arrival_date TIMESTAMP,
            fare DECIMAL,
            travel_class VARCHAR(20)
        );
    """
    conn_db = get_airindia_db_connection()
    cur = conn_db.cursor()
    cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", ("airindiaflights",))
    if not cur.fetchone()[0]:
        cur.execute(create_table_query)
        conn_db.commit()

    # Insert flight data into the database
    insert_query = """
        INSERT INTO AirIndiaFlights (
            source_airport, destination_airport, flight_number, 
            departure_date, arrival_date, fare, travel_class
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    for flight in flights:
        for segment in flight.get("itineraries", []):
            for leg in segment.get("legs", []):
                values = (
                    leg.get("origin", {}).get("iataCode", source_airport_code),
                    leg.get("destination", {}).get("iataCode", destination_airport_code),
                    leg.get("flightNumber", ""),
                    datetime.fromisoformat(leg.get("departureDateTime", datetime.now().isoformat())),
                    datetime.fromisoformat(leg.get("arrivalDateTime", datetime.now().isoformat())),
                    flight.get("price", {}).get("total", 0.0),
                    flight.get("cabinClass", "economy").upper()
                )
                # Debug: Print values to verify structure before inserting
                print(f"Inserting values: {values}")
                cur.execute(insert_query, values)

    conn_db.commit()
    cur.close()
    conn_db.close()
    print("Data inserted successfully into AirIndiaFlights.")
    

def fetch_spicejet_flights(source_airport_code, destination_airport_code, journey_date):
    conn = http.client.HTTPSConnection("tripadvisor16.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': "139be57d39msh8396d6c2824a3e8p155bc8jsn25b210898778",
        'x-rapidapi-host': "tripadvisor16.p.rapidapi.com"
    }

    # API endpoint for Trip-Advisor-SpiceJet
    api_endpoint = (
        f"/api/v1/flights/searchFlights?"
        f"sourceAirportCode={source_airport_code}&destinationAirportCode={destination_airport_code}"
        f"&date={journey_date}&itineraryType=ONE_WAY&sortOrder=BEST_VALUE"
        f"&numAdults=1&classOfService=ECONOMY&pageNumber=1&currencyCode=INR&airlines=SG"
    )
    
    conn.request("GET", api_endpoint, headers=headers)
    
    res = conn.getresponse()
    if res.status != 200:
        raise Exception(f"API call failed with status {res.status}")
    
    data = res.read()
    flights_data = json.loads(data.decode("utf-8"))
    
    # Parse flight data (adjust fields based on the new response structure)
    flights = flights_data.get("data", {}).get("flights", [])
    if not flights:
        print("No flights found for SpiceJet.")
        return

    # Ensure database table exists
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
    conn_db = get_spicejet_db_connection()
    cur = conn_db.cursor()
    cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", ("spicejetflights",))
    if not cur.fetchone()[0]:
        cur.execute(create_table_query)
        conn_db.commit()

    # Insert flight data into the database
    insert_query = """
        INSERT INTO SpiceJetFlights (
            source_city, destination_city, flight_number, 
            departure_date, arrival_time, fare, class
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    for flight in flights:
        for segment in flight["segments"]:
            for leg in segment["legs"]:
                values = (
                    leg.get("originStationCode", ""),
                    leg.get("destinationStationCode", ""),
                    leg.get("flightNumber", ""),
                    datetime.fromisoformat(leg.get("departureDateTime", datetime.now().isoformat())),
                    datetime.fromisoformat(leg.get("arrivalDateTime", datetime.now().isoformat())),
                    flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
                    leg.get("classOfService", "ECONOMY")
                )
                # Debug: Print values to verify structure before inserting
                print(f"Inserting values: {values}")
                cur.execute(insert_query, values)

    conn_db.commit()
    cur.close()
    conn_db.close()
    print("Data inserted successfully into SpiceJetFlights.")