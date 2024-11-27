import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
from config import get_skyscanner_db_connection

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
            Source_Airport_Name VARCHAR(255),
            Destination_City VARCHAR(255),
            Destination_Airport_Name VARCHAR(255),
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

# Function to fetch flights data
def get_skyScanner_flights(source, destination, travel_date):
    # Get Airport code
    srcCode= get_airport_code(source)
    dstCode= get_airport_code(destination)
    
    # Format the date as required by the API
    formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    conn = http.client.HTTPSConnection("sky-scanner3.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': "3254875c10mshf948cf35f09d589p1c7181jsn2faeb668170d",
        'x-rapidapi-host': "sky-scanner3.p.rapidapi.com"
    }

    # API request
    endpoint = f"/flights/search-one-way?fromEntityId={srcCode}&toEntityId={dstCode}&departDate={formatted_date}&currency=INR&cabinClass=economy"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    response = json.loads(data.decode("utf-8"))

    # Extract details
    itineraries = response.get("data", {}).get("itineraries", [])
    flights = []

    for itinerary in itineraries:
        price = itinerary.get("price", {}).get("raw", "N/A")
        legs = itinerary.get("legs", [])
        
        for leg in legs:
            flight_details = {
                "Airlines": leg.get("carriers", {}).get("marketing", [{}])[0].get("name", "N/A"),
                "Source_City": leg.get("origin", {}).get("city", "N/A"),
                "Source_Airport_Name": leg.get("origin", {}).get("name", "N/A"),
                "Destination_City": leg.get("destination", {}).get("city", "N/A"),
                "Destination_Airport_Name": leg.get("destination", {}).get("name", "N/A"),
                "Departure_Date": leg.get("departure", "").split("T")[0],
                "Departure_Time": leg.get("departure", "").split("T")[1] if "T" in leg.get("departure", "") else None,
                "Arrival_Date": leg.get("arrival", "").split("T")[0],
                "Arrival_Time": leg.get("arrival", "").split("T")[1] if "T" in leg.get("arrival", "") else None,
                "Duration_of_Travel": f"{leg.get('durationInMinutes', 'N/A')} minutes",
                "Flight_Number": leg.get("segments", [{}])[0].get("flightNumber", "N/A"),
                "Price_in_INR": f"₹ {float(price):.2f}" if price != "N/A" else "N/A"
            }
            flights.append(flight_details)
    
    return flights

# Function to insert flight data into the database
def insert_flights_data(flights):
    try:
        conn = get_skyscanner_db_connection()
        cursor = conn.cursor()
        
        # SQL command to insert data
        insert_query = """
        INSERT INTO FlightsData (
            Airlines, Source_City, Source_Airport_Name, Destination_City,
            Destination_Airport_Name, Departure_Date, Departure_Time,
            Arrival_Date, Arrival_Time, Duration_of_Travel, Flight_Number, Price_in_INR
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        
        for flight in flights:
            cursor.execute(insert_query, (
                flight["Airlines"], flight["Source_City"], flight["Source_Airport_Name"],
                flight["Destination_City"], flight["Destination_Airport_Name"],
                flight["Departure_Date"], flight["Departure_Time"], flight["Arrival_Date"],
                flight["Arrival_Time"], flight["Duration_of_Travel"], flight["Flight_Number"],
                flight["Price_in_INR"]
            ))
        
        conn.commit()
        print(f"{len(flights)} flight records inserted successfully.")
        
    except Exception as e:
        print("Error inserting flight data:", e)
        
    finally:
        if conn:
            cursor.close()
            conn.close()

# Main function
if __name__ == "__main__":
    # Create the table
    create_flights_table()
    
    # Example inputs
    source = "Bumbae"  
    destination = "Vishakaptnam" 
    formatted_date = "2024-12-26"
    
    # Fetch flight data
    flights = get_skyScanner_flights(source, destination, formatted_date)
    
    # Insert data into the database
    insert_flights_data(flights)