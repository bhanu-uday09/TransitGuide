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

def make_api_request(endpoint):
    conn = http.client.HTTPSConnection("tripadvisor16.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': "3254875c10mshf948cf35f09d589p1c7181jsn2faeb668170d",
        'x-rapidapi-host': "tripadvisor16.p.rapidapi.com"
    }

    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    if res.status != 200:
        raise Exception(f"API call failed with status {res.status}")
    data = res.read()
    return json.loads(data.decode("utf-8"))

def data_exists_in_global_flights(source, destination, journey_date):
    """
    Check if data for the given source, destination, and journey date exists in the global_flights table.
    """
    query = """
        SELECT 1 FROM global_flights
        WHERE source_city = %s AND destination_city = %s AND departure_date::date = %s
        LIMIT 1;
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, (source, destination, journey_date))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"Error checking data existence in global_flights: {e}")
        return False

# 1. Indigo Flights Function
def fetch_indigo_flights(source_airport_code, destination_airport_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_airport_code}"
        f"&destinationAirportCode={destination_airport_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=USD&airlines=6E"
    )
    print(api_endpoint)
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
    try:
        conn = get_indigo_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", 
                    (create_table_query.split()[5].lower(),))
        if not cur.fetchone()[0]:
            print("Creating table...")
            cur.execute(create_table_query)
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error ensuring table exists: {str(e)}")

    response = make_api_request(api_endpoint)
    flights = response.get("data", {}).get("flights", [])

    if not flights:
        print("No flights found for Indigo.")
        return

    try:
        conn = get_indigo_db_connection()
        cur = conn.cursor()
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

                    # Debug: Print values to check structure before inserting
                    print(f"Inserting values into IndigoFlights: {values}")
                    cur.execute(insert_query, values)

        conn.commit()
        cur.close()
        conn.close()
        print("Data inserted successfully into IndigoFlights.")
    except Exception as e:
        print(f"Error inserting data into IndigoFlights: {str(e)}")

# 2. SpiceJet Flights Function
def fetch_spicejet_flights(source_airport_code, destination_airport_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_airport_code}"
        f"&destinationAirportCode={destination_airport_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=USD&airlines=SG"
    )
    
    create_table_query = """
        CREATE TABLE IF NOT EXISTS SpiceJetFlights (
            id SERIAL PRIMARY KEY,
            source_city VARCHAR(10),
            destination_city VARCHAR(10),
            flight_number VARCHAR(10),
            departure_date TIMESTAMP,
            arrival_time TIMESTAMP,
            aircraft_type VARCHAR(50),
            duration INT,
            fare DECIMAL,
            class VARCHAR(20),
            baggage_allowance VARCHAR(50),
            seat_availability VARCHAR(50)
        );
    """
    try:
        conn = get_spicejet_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", 
                    (create_table_query.split()[5].lower(),))
        if not cur.fetchone()[0]:
            print("Creating table...")
            cur.execute(create_table_query)
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error ensuring table exists: {str(e)}")

    print(api_endpoint)
    response = make_api_request(api_endpoint)
    flights = response.get("data", {}).get("flights", [])

    if not flights:
        print("No flights found for SpiceJet.")
        return

    try:
        conn = get_spicejet_db_connection()
        cur = conn.cursor()
        insert_query = """
            INSERT INTO SpiceJetFlights (
                source_city, destination_city, flight_number, 
                departure_date, arrival_time, aircraft_type, 
                duration, fare, class, baggage_allowance, 
                seat_availability
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        leg.get("aircraftType", "Unknown"),
                        leg.get("durationMinutes", 0),
                        flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
                        leg.get("classOfService", "ECONOMY"),
                        leg.get("baggageAllowance", "Not Available"),
                        leg.get("seatAvailability", "Not Available")
                    )
                    
                    # Debug: Print the values to confirm structure
                    print(f"Inserting values into SpiceJetFlights: {values}")
                    cur.execute(insert_query, values)

        conn.commit()
        cur.close()
        conn.close()
        print("Data inserted successfully into SpiceJetFlights.")
    except Exception as e:
        print(f"Error inserting data into SpiceJetFlights: {str(e)}")

# 3. Air India Flights Function
def fetch_air_india_flights(source_airport_code, destination_airport_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_airport_code}"
        f"&destinationAirportCode={destination_airport_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=AI"
    )
    create_table_query = """
        CREATE TABLE IF NOT EXISTS AirIndiaFlights (
            id SERIAL PRIMARY KEY,
            origin_airport VARCHAR(10),
            destination_airport VARCHAR(10),
            flight_no VARCHAR(10),
            departure_timestamp TIMESTAMP,
            arrival_timestamp TIMESTAMP,
            flight_duration INT,
            fare DECIMAL,
            travel_class VARCHAR(20),
            meal_option BOOLEAN,
            cancellation_policy TEXT
        );
    """
    try:
        conn = get_airindia_db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", 
                    (create_table_query.split()[5].lower(),))
        if not cur.fetchone()[0]:
            print("Creating table...")
            cur.execute(create_table_query)
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error ensuring table exists: {str(e)}")

    response = make_api_request(api_endpoint)
    flights = response.get("data", {}).get("flights", [])

    if not flights:
        print("No flights found for Air India.")
        return

    try:
        conn = get_airindia_db_connection()
        cur = conn.cursor()
        insert_query = """
            INSERT INTO AirIndiaFlights (
                origin_airport, destination_airport, flight_no, 
                departure_timestamp, arrival_timestamp, flight_duration, 
                fare, travel_class, meal_option, cancellation_policy
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        leg.get("durationMinutes", 0),
                        flight["purchaseLinks"][0].get("totalPricePerPassenger", 0.0),
                        leg.get("classOfService", "ECONOMY"),
                        leg.get("mealOption", False),
                        flight.get("cancellationPolicy", "No policy available")
                    )
                    cur.execute(insert_query, values)

        conn.commit()
        cur.close()
        conn.close()
        print("Data inserted successfully into AirIndiaFlights.")
    except Exception as e:
        print(f"Error inserting data into AirIndiaFlights: {str(e)}")
        

#4 global view
def get_flights(source, destination, journey_date, sort_order, class_of_service):
    try:
        conn = get_globalview_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT flight_number, source_city, destination_city, departure_date, arrival_time, fare, class, airline
            FROM global_flights
            WHERE source_city = %s AND destination_city = %s AND departure_date = %s AND class = %s
            ORDER BY
                CASE
                    WHEN %s = 'ML_BEST_VALUE' THEN fare
                    WHEN %s = 'ML_LOWEST_PRICE' THEN fare
                    WHEN %s = 'ML_QUICKEST' THEN departure_date
                END
            LIMIT 50;
        """
        cursor.execute(query, (source, destination, journey_date, class_of_service, sort_order, sort_order, sort_order))
        results = cursor.fetchall()
        conn.close()

        flights = []
        for row in results:
            flights.append({
                "flight_number": row[0],
                "source_city": row[1],
                "destination_city": row[2],
                "departure_date": row[3],
                "arrival_time": row[4],
                "fare": row[5],
                "class": row[6],
                "airline": row[7],
            })
        return flights
    except Exception as e:
        print(f"Error querying global flights: {e}")
        return []
    
