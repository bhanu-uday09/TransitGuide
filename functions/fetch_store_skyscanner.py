import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
import psycopg2

def get_skyscanner_db_connection():
    return psycopg2.connect("dbname=SkyScannerDB user=postgres password=0000")


# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code','railway_station_code'])

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


# Function to create the FlightsData table
def create_flights_table():
    try:
        conn = get_skyscanner_db_connection()
        cursor = conn.cursor()
        
        # SQL command to create the table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS FlightsData (
            id SERIAL PRIMARY KEY,
            Airlines VARCHAR(255),
            Source_City VARCHAR(255),
            Source_Airport_Code VARCHAR(255),
            Destination_City VARCHAR(255),
            Destination_Airport_Code VARCHAR(255),
            Departure_Date DATE,
            Departure_Time TIME,
            Arrival_Date DATE,
            Arrival_Time TIME,
            Duration_of_Travel VARCHAR(50),
            Flight_Number VARCHAR(50),
            Price_in_INR VARCHAR(50)
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("Table FlightsData created successfully.")
        
    except Exception as e:
        print("Error creating table:", e)
        
    finally:
        if conn:
            cursor.close()
            conn.close()

# Function to fetch flights from SkyScanner
def get_skyScanner_flights(source, destination, travel_date):
    
    formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    conn = http.client.HTTPSConnection("sky-scanner3.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': "3254875c10mshf948cf35f09d589p1c7181jsn2faeb668170d",
        'x-rapidapi-host': "sky-scanner3.p.rapidapi.com"
    }
    
    endpoint = f"/flights/search-one-way?fromEntityId={source}&toEntityId={destination}&departDate={formatted_date}&currency=INR&cabinClass=economy"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    
    try:
        response = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("Error decoding the API response.")
        return
    
    # Create the FlightsData table
    create_table_query = """
    CREATE TABLE IF NOT EXISTS FlightsData (
        id SERIAL PRIMARY KEY,
        Airlines VARCHAR(255),
        Source_City VARCHAR(255),
        Source_Airport_Code VARCHAR(255),
        Destination_City VARCHAR(255),
        Destination_Airport_Code VARCHAR(255),
        Departure_Date DATE,
        Departure_Time TIME,
        Arrival_Date DATE,
        Arrival_Time TIME,
        Duration_of_Travel VARCHAR(50),
        Flight_Number VARCHAR(50),
        Price_in_INR VARCHAR(50)
    );
    """
    try:
        connection = get_skyscanner_db_connection()
        if not connection:
            return
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
    except Exception as e:
        print(f"Error creating table: {e}")
        return

    # Extract flight details
    itineraries = response.get("data", {}).get("itineraries", [])
    flights = []
    for itinerary in itineraries:
        price = itinerary.get("price", {}).get("raw", "N/A")
        legs = itinerary.get("legs", [])
        for leg in legs:
            flights.append((
                leg.get("carriers", {}).get("marketing", [{}])[0].get("name", "N/A"),
                leg.get("origin", {}).get("city", "N/A"),
                leg.get("origin", {}).get("displayCode", "N/A"),
                leg.get("destination", {}).get("city", "N/A"),
                leg.get("destination", {}).get("displayCode", "N/A"),
                leg.get("departure", "").split("T")[0],
                leg.get("departure", "").split("T")[1] if "T" in leg.get("departure", "") else None,
                leg.get("arrival", "").split("T")[0],
                leg.get("arrival", "").split("T")[1] if "T" in leg.get("arrival", "") else None,
                f"{leg.get('durationInMinutes', 'N/A')} minutes",
                leg.get("segments", [{}])[0].get("flightNumber", "N/A"),
                f"₹ {float(price):.2f}" if price != "N/A" else "N/A"
            ))
    
    # Insert data into the database
    if flights:
        insert_query = """
        INSERT INTO FlightsData (
            Airlines, Source_City, Source_Airport_Code, Destination_City,
            Destination_Airport_Code, Departure_Date, Departure_Time,
            Arrival_Date, Arrival_Time, Duration_of_Travel, Flight_Number, Price_in_INR
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.executemany(insert_query, flights)
            print(f"{len(flights)} rows inserted into FlightsData successfully.")
        except Exception as e:
            print(f"Error inserting data: {e}")
    else:
        print("No flights to insert.")
        
        
        
# get_skyScanner_flights('BOM','HYD','2024-12-27')