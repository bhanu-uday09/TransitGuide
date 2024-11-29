import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
import psycopg2

def get_priceline_db_connection():
    return psycopg2.connect("dbname=PriceLineDB user=postgres password=0000")


# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code','railway_station_code'])

# Load airline data into a dictionary
airline_data = {
    "6E": "IndiGo",
    "AI": "Air India",
    "IX": "Air India Express",
    "SG": "SpiceJet",
    "G8": "Go First",
    "I5": "AirAsia India",
    "9I": "Alliance Air",
    "S5": "Star Air",
    "QP": "Akasa Air"
}


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


# get_closest_city('Hydrabad')


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
    
    
# get_airport_code("Bumbai")


# Function to fetch and store flight data
def get_priceline_flights(source, destination, formatted_date):
    # API connection setup
    conn = http.client.HTTPSConnection("priceline-com2.p.rapidapi.com")
    headers = {
        'x-rapidapi-key': "3254875c10mshf948cf35f09d589p1c7181jsn2faeb668170d",
        'x-rapidapi-host': "priceline-com2.p.rapidapi.com"
    }
    endpoint = f"/flights/search-one-way?originAirportCode={source}&destinationAirportCode={destination}&departureDate={formatted_date}&numOfStops=0"

    # Fetch data from API
    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        response = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("Error decoding the API response.")
        return
    except Exception as e:
        print(f"Error fetching data from API: {e}")
        return

    # Extract flight listings
    listings = response.get("data", {}).get("listings", [])
    if not listings:
        print("No flight listings found.")
        return

    # Create the FlightsInfo table if not exists
    create_table_query = """
    CREATE TABLE IF NOT EXISTS FlightsInfo (
        Airlines TEXT,
        Flight_Number TEXT,
        Source_City TEXT,
        Source_Airport_Code TEXT,
        Destination_City TEXT,
        Destination_Airport_Code TEXT,
        Departure_Date DATE,
        Departure_Time TIME,
        Arrival_Date DATE,
        Arrival_Time TIME,
        Duration_of_Travel TEXT,
        Stop_Quantity INTEGER,
        Equipment_Name TEXT,
        Price_in_INR TEXT
    );
    """
    try:
        connection = get_priceline_db_connection()
        if not connection:
            return
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
    except Exception as e:
        print(f"Error creating table: {e}")
        return

    # Prepare flight data
    flights = []
    for listing in listings:
        slices = listing.get("slices", [])
        price_usd = listing.get("totalPriceWithDecimal", {}).get("price", "N/A")
        try:
            price_inr = float(price_usd) * 84.46 if price_usd != "N/A" else None
        except ValueError:
            price_inr = None

        for slice_data in slices:
            segments = slice_data.get("segments", [])
            for segment in segments:
                airline_code = segment.get("marketingAirline", "N/A")
                airline_name = airline_data.get(airline_code, "Unknown")
                if airline_name == "Unknown":
                    airline_name = "Akasa Air"  # Replace 'Unknown' with 'Akasa Air'
                date_time_depart = segment.get("departInfo", {}).get("time", {}).get("dateTime", "")
                date_time_arrival = segment.get("arrivalInfo", {}).get("time", {}).get("dateTime", "")

                flight_details = {
                    "Airlines": airline_name,
                    "Flight_Number": segment.get("flightNumber", "N/A"),
                    "Source_City": segment.get("departInfo", {}).get("airport", {}).get("name", "N/A"),
                    "Source_Airport_Code": segment.get("departInfo", {}).get("airport", {}).get("code", "N/A"),
                    "Destination_City": segment.get("arrivalInfo", {}).get("airport", {}).get("name", "N/A"),
                    "Destination_Airport_Code": segment.get("arrivalInfo", {}).get("airport", {}).get("code", "N/A"),
                    "Departure_Date": date_time_depart.split("T")[0] if "T" in date_time_depart else "N/A",
                    "Departure_Time": date_time_depart.split("T")[1] if "T" in date_time_depart else "N/A",
                    "Arrival_Date": date_time_arrival.split("T")[0] if "T" in date_time_arrival else "N/A",
                    "Arrival_Time": date_time_arrival.split("T")[1] if "T" in date_time_arrival else "N/A",
                    "Duration_of_Travel": f"{segment.get('duration', 'N/A')} minutes",
                    "Stop_Quantity": segment.get("stopQuantity", 0),
                    "Equipment_Name": segment.get("equipmentName", "N/A"),
                    "Price_in_INR": f"₹ {price_inr:.2f}" if price_inr is not None else "N/A"
                }
                flights.append(flight_details)

    # Insert flight data
    if flights:
        insert_query = """
        INSERT INTO FlightsInfo (
            Airlines, Flight_Number, Source_City, Source_Airport_Code,
            Destination_City, Destination_Airport_Code, Departure_Date,
            Departure_Time, Arrival_Date, Arrival_Time, Duration_of_Travel,
            Stop_Quantity, Equipment_Name, Price_in_INR
        ) VALUES (
            %(Airlines)s, %(Flight_Number)s, %(Source_City)s, %(Source_Airport_Code)s,
            %(Destination_City)s, %(Destination_Airport_Code)s, %(Departure_Date)s,
            %(Departure_Time)s, %(Arrival_Date)s, %(Arrival_Time)s, %(Duration_of_Travel)s,
            %(Stop_Quantity)s, %(Equipment_Name)s, %(Price_in_INR)s
        );
        """
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.executemany(insert_query, flights)
            print(f"{len(flights)} rows inserted into FlightsInfo successfully.")
        except Exception as e:
            print(f"Error inserting data: {e}")
    else:
        print("No flights to insert.")
        
        
get_priceline_flights('RPR','BOM','2024-12-24')