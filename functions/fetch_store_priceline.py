import http.client
import json
from datetime import datetime
import pandas as pd
from rapidfuzz import process, fuzz
from config import get_priceline_db_connection

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

# Function to create the FlightsInfo table
def create_flights_table():
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
            print("Failed to connect to the database.")
            return

        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()

        print("Table FlightsInfo created or already exists.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error creating table: {e}")


# Function to insert flight data into the FlightsInfo table
def insert_flight_data(flights):
    insert_query = """
    INSERT INTO FlightsInfo (
        Airlines, Flight_Number, Source_City, Source_Airport_Code,
        Destination_City, Destination_Airport_Code, Departure_Date,
        Departure_Time, Arrival_Date, Arrival_Time, Duration_of_Travel,
        Stop_Quantity, Equipment_Name, Price_in_INR
    ) VALUES (
        %(Airlines)s, %(Flight Number)s, %(Source City)s, %(Source Airport Code)s,
        %(Destination City)s, %(Destination Airport Code)s, %(Departure Date)s,
        %(Departure Time)s, %(Arrival Date)s, %(Arrival Time)s, %(Duration of Travel)s,
        %(Stop Quantity)s, %(Equipment Name)s, %(Price in INR)s
    );
    """
    try:
        connection = get_priceline_db_connection()
        if not connection:
            print("Failed to connect to the database.")
            return

        cursor = connection.cursor()

        # Insert each flight into the database
        for flight in flights:
            cursor.execute(insert_query, flight)

        connection.commit()

        print(f"{len(flights)} rows inserted into FlightsInfo successfully.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inserting data: {e}")


# Function to fetch flights data
def get_PriceLine_flights(source, destination, formatted_date):
    # API connection setup
    conn = http.client.HTTPSConnection("priceline-com2.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': "3254875c10mshf948cf35f09d589p1c7181jsn2faeb668170d",
        'x-rapidapi-host': "priceline-com2.p.rapidapi.com"
    }

    # API request
    endpoint = f"/flights/search-one-way?originAirportCode={source}&destinationAirportCode={destination}&departureDate={formatted_date}&numOfStops=0"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()

    # Parse the API response
    try:
        response = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("Error decoding the API response.")
        return

    # Extract details
    listings = response.get("data", {}).get("listings", [])
    if not listings:
        print("No flight listings found.")
        return

    flights = []

    for listing in listings:
        slices = listing.get("slices", [])
        price_usd = listing.get("totalPriceWithDecimal", {}).get("price", "N/A")
        try:
            price_inr = float(price_usd) * 84.46 if price_usd != "N/A" else "N/A"
        except ValueError:
            price_inr = "N/A"

        for slice_data in slices:
            segments = slice_data.get("segments", [])
            total_duration = slice_data.get("durationInMinutes", "N/A")

            for segment in segments:
                flight_details = {
                    "Airlines": segment.get("marketingAirline", "N/A"),
                    "Flight Number": segment.get("flightNumber", "N/A"),
                    "Source City": segment.get("departInfo", {}).get("airport", {}).get("name", "N/A"),
                    "Source Airport Code": segment.get("departInfo", {}).get("airport", {}).get("code", "N/A"),
                    "Destination City": segment.get("arrivalInfo", {}).get("airport", {}).get("name", "N/A"),
                    "Destination Airport Code": segment.get("arrivalInfo", {}).get("airport", {}).get("code", "N/A"),
                    "Departure Date": segment.get("departInfo", {}).get("time", {}).get("dateTime", "").split("T")[0],
                    "Departure Time": segment.get("departInfo", {}).get("time", {}).get("dateTime", "").split("T")[1] if "T" in segment.get("departInfo", {}).get("time", {}).get("dateTime", "") else "N/A",
                    "Arrival Date": segment.get("arrivalInfo", {}).get("time", {}).get("dateTime", "").split("T")[0],
                    "Arrival Time": segment.get("arrivalInfo", {}).get("time", {}).get("dateTime", "").split("T")[1] if "T" in segment.get("arrivalInfo", {}).get("time", {}).get("dateTime", "") else "N/A",
                    "Duration of Travel": f"{segment.get('duration', 'N/A')} minutes",
                    "Stop Quantity": segment.get("stopQuantity", 0),
                    "Equipment Name": segment.get("equipmentName", "N/A"),
                    "Price in INR": f"₹ {price_inr:.2f}" if price_inr != "N/A" else "N/A"
                }
                flights.append(flight_details)

    # Insert data into the database
    if flights:
        insert_flight_data(flights)
    else:
        print("No flights found.")


# Main execution
if __name__ == "__main__":
    create_flights_table()  # Ensure table is created
    source = input("Enter source airport code: ").strip().upper()
    destination = input("Enter destination airport code: ").strip().upper()
    travel_date = input("Enter travel date (YYYY-MM-DD): ").strip()
    formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    get_PriceLine_flights(source, destination, formatted_date)