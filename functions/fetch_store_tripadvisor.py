import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
import psycopg2

def get_tripadvisor_db_connection():
    return psycopg2.connect("dbname=TripAdvisorDB user=postgres password=0000")

# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code', 'railway_station_code'])


def get_closest_city(user_city):
    """
    Find the closest matching city to the user's input using fuzzy matching.
    """
    try:
        city_list = airport_df['city'].tolist()

        closest_match, score, _ = process.extractOne(
            user_city.strip().title(), city_list, scorer=fuzz.ratio
        )

        print(f"Input: {user_city}, Closest Match: {closest_match}, Score: {score}")

        if score >= 50:
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
        closest_city = get_closest_city(user_city)
        if closest_city:
            result = airport_df[airport_df['city'] == closest_city]['airport_code']
            return result.iloc[0] if not result.empty else None
        else:
            return None
    except Exception as e:
        print(f"Error fetching airport code for {user_city}: {e}")
        return None



#  Function to fetch and store flights from TripAdvisor
def get_tripadvisor_flights(source, destination, formatted_date):
    conn = http.client.HTTPSConnection("tripadvisor16.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': "3254875c10mshf948cf35f09d589p1c7181jsn2faeb668170d",
        'x-rapidapi-host': "tripadvisor16.p.rapidapi.com"
    }

    endpoint = f"/api/v1/flights/searchFlights?sourceAirportCode={source}&destinationAirportCode={destination}&date={formatted_date}&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1&numSeniors=0&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()

    try:
        response = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("Error decoding the API response.")
        return

    # Extract flight data
    flights_data = response.get("data", {}).get("flights", [])
    if not flights_data:
        print("No flight data available.")
        return

    # Create the FlightsDetails table
    create_table_query = """
    CREATE TABLE IF NOT EXISTS FlightDetails (
        Airline_Name TEXT,
        Source_City_Airport_Code TEXT,
        Destination_City_Airport_Code TEXT,
        Departure_Date_Time TIMESTAMP,
        Arrival_Date_Time TIMESTAMP,
        Flight_Class TEXT,
        Flight_Number TEXT,
        Number_of_Stops INTEGER,
        Distance_KM FLOAT,
        Price_INR TEXT
    );
    """
    try:
        connection = get_tripadvisor_db_connection()
        if not connection:
            return
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
    except Exception as e:
        print(f"Error creating table: {e}")
        return

    # Process flight details
    flights = []
    for flight in flights_data:
        purchase_links = flight.get("purchaseLinks", [])
        price_usd = purchase_links[0].get("totalPrice", "N/A") if purchase_links else "N/A"
        try:
            price_inr = float(price_usd) * 84.46 if price_usd != "N/A" else "N/A"
        except ValueError:
            price_inr = "N/A"

        for segment in flight.get("segments", []):
            for leg in segment.get("legs", []):
                departure_datetime = leg.get("departureDateTime")
                arrival_datetime = leg.get("arrivalDateTime")
                
                flight_details = (
                    leg.get("marketingCarrier", {}).get("displayName", "N/A"),
                    leg.get("originStationCode", "N/A"),
                    leg.get("destinationStationCode", "N/A"),
                    departure_datetime if departure_datetime else None,
                    arrival_datetime if arrival_datetime else None,
                    leg.get("classOfService", "N/A"),
                    leg.get("flightNumber", "N/A"),
                    leg.get("numStops", 0),
                    leg.get("distanceInKM", 0.0),
                    f"₹ {price_inr:.2f}" if price_inr != "N/A" else "N/A"
                )
                flights.append(flight_details)

    # Insert data into the database
    if flights:
        insert_query = """
        INSERT INTO FlightDetails (
            Airline_Name, Source_City_Airport_Code, Destination_City_Airport_Code,
            Departure_Date_Time, Arrival_Date_Time, Flight_Class, Flight_Number,
            Number_of_Stops, Distance_KM, Price_INR
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.executemany(insert_query, flights)
            print(f"{len(flights)} flights inserted into FlightDetails successfully.")
        except Exception as e:
            print(f"Error inserting data: {e}")
    else:
        print("No flights to insert.")
        
        
# get_tripadvisor_flights('DEL','HYD','2024-12-26')