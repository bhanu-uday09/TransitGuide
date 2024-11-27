import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
from config import get_tripadvisor_db_connection

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


def create_flightdetails_table():
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
            print("Failed to connect to the database.")
            return
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        print("Table FlightDetails created or already exists.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error creating table: {e}")


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

    flights_data = response.get("data", {}).get("flights", [])
    if not flights_data:
        print("No flight data available.")
        return

    insert_query = """
    INSERT INTO FlightDetails (
        Airline_Name, Source_City_Airport_Code, Destination_City_Airport_Code,
        Departure_Date_Time, Arrival_Date_Time, Flight_Class, Flight_Number,
        Number_of_Stops, Distance_KM, Price_INR
    ) VALUES (
        %(Airline Name)s, %(Source City/Airport Code)s, %(Destination City/Airport Code)s,
        %(Departure Date/Time)s, %(Arrival Date/Time)s, %(Flight Class)s, %(Flight Number)s,
        %(Number of Stops)s, %(Distance_KM)s, %(Price_INR)s
    );
    """

    flights = []

    try:
        connection = get_tripadvisor_db_connection()
        if not connection:
            print("Failed to connect to the database.")
            return

        cursor = connection.cursor()

        for flight in flights_data:
            purchase_links = flight.get("purchaseLinks", [])
            price_usd = purchase_links[0].get("totalPrice", "N/A") if purchase_links else "N/A"
            try:
                price_inr = float(price_usd) * 84.46 if price_usd != "N/A" else "N/A"
            except ValueError:
                price_inr = "N/A"

            for segment in flight.get("segments", []):
                for leg in segment.get("legs", []):
                    flight_details = {
                        "Airline Name": leg.get("marketingCarrier", {}).get("displayName", "N/A"),
                        "Source City/Airport Code": leg.get("originStationCode", "N/A"),
                        "Destination City/Airport Code": leg.get("destinationStationCode", "N/A"),
                        "Departure Date/Time": leg.get("departureDateTime", None),
                        "Arrival Date/Time": leg.get("arrivalDateTime", None),
                        "Flight Class": leg.get("classOfService", "N/A"),
                        "Flight Number": leg.get("flightNumber", "N/A"),
                        "Number of Stops": leg.get("numStops", 0),
                        "Distance_KM": leg.get("distanceInKM", 0.0),
                        "Price_INR": f"₹ {price_inr:.2f}" if price_inr != "N/A" else "N/A"
                    }
                    flights.append(flight_details)

                    cursor.execute(insert_query, flight_details)

        connection.commit()
        print(f"{len(flights)} flights inserted into FlightDetails successfully.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error processing or inserting data: {e}")


if __name__ == "__main__":
    create_flightdetails_table()
    source = input("Enter source city or airport code: ").strip()
    destination = input("Enter destination city or airport code: ").strip()
    travel_date = input("Enter travel date (YYYY-MM-DD): ").strip()
    formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    get_tripadvisor_flights(source, destination, formatted_date)