import http.client
import json
from datetime import datetime
from config import get_db_connection

def get_airport_code(city):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT airport_code FROM AirportData WHERE city = %s LIMIT 1", (city,))
            result = cur.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error fetching airport code for {city}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def make_api_request(endpoint):
    conn = http.client.HTTPSConnection("tripadvisor16.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': "139be57d39msh8396d6c2824a3e8p155bc8jsn25b210898778",
        'x-rapidapi-host': "tripadvisor16.p.rapidapi.com"
    }

    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    if res.status != 200:
        raise Exception(f"API call failed with status {res.status}")
    data = res.read()
    return json.loads(data.decode("utf-8"))

def ensure_table_exists(create_table_query):
    try:
        conn = get_db_connection()
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

# 1. Indigo Flights Function
def fetch_indigo_flights(source_airport_code, destination_airport_code, journey_date):
    api_endpoint = (
        f"/api/v1/flights/searchFlights?sourceAirportCode={source_airport_code}"
        f"&destinationAirportCode={destination_airport_code}&date={journey_date}"
        f"&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1"
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=6E"
    )
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
    ensure_table_exists(create_table_query)

    response = make_api_request(api_endpoint)
    flights = response.get("data", {}).get("flights", [])

    if not flights:
        print("No flights found for Indigo.")
        return

    try:
        conn = get_db_connection()
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
        f"&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=SG"
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
    ensure_table_exists(create_table_query)

    print(api_endpoint)
    response = make_api_request(api_endpoint)
    flights = response.get("data", {}).get("flights", [])

    if not flights:
        print("No flights found for SpiceJet.")
        return

    try:
        conn = get_db_connection()
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
    ensure_table_exists(create_table_query)

    response = make_api_request(api_endpoint)
    flights = response.get("data", {}).get("flights", [])

    if not flights:
        print("No flights found for Air India.")
        return

    try:
        conn = get_db_connection()
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
        
        
        
