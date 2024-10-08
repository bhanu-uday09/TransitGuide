from flask import Flask, render_template, request
import psycopg2
import http.client
import json
from datetime import datetime

app = Flask(__name__)

# Database connection
def get_db_connection():
    conn = psycopg2.connect("dbname=TransitGuide user=postgres password=0000")
    return conn

# Search for airport code by city name
def get_airport_code(city):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT airport_code FROM AirportData WHERE city = %s LIMIT 1", (city,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else None


def fetch_flights(source_airport_code, destination_airport_code, journey_date):
    # Step 1: Fetch Data from the API
    conn = http.client.HTTPSConnection("tripadvisor16.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': "939577bcd4msh51c844c189119f7p129984jsnf3e058bd1f56",  # Replace with your actual API key
        'x-rapidapi-host': "tripadvisor16.p.rapidapi.com"
    }

    # Construct the API endpoint
    api_endpoint = f"/api/v1/flights/searchFlights?sourceAirportCode={source_airport_code}&destinationAirportCode={destination_airport_code}&date={journey_date}&itineraryType=ONE_WAY&sortOrder=ML_BEST_VALUE&numAdults=1&numSeniors=0&classOfService=ECONOMY&pageNumber=1&nearby=yes&nonstop=yes&currencyCode=INR&airlines=6E"

    print(api_endpoint)
    
    # Make API request
    conn.request("GET", api_endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    decoded_data = data.decode("utf-8")

    # Parse JSON response
    response = json.loads(decoded_data)

    # Step 2: Connect to PostgreSQL
    db_conn = psycopg2.connect("dbname=TransitGuide user=postgres password=0000")
    cur = db_conn.cursor()

    # SQL Insert Query
    insert_query = """
        INSERT INTO IndigoFlightsTable (source, destination, flight_number, departure_date, departure_time, arrival_time, fare, class)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """

    # Step 3: Parse and Insert Data
    flights = response.get('data', {}).get('flights', [])

    if not flights:
        print("No flights available for the given parameters.")
        return

    for flight in flights:
        for segment in flight['segments']:
            for leg in segment['legs']:
                source = leg['originStationCode']
                destination = leg['destinationStationCode']
                flight_number = leg['flightNumber']
                
                # Convert departure and arrival to separate date and time
                departure_datetime = datetime.fromisoformat(leg['departureDateTime'])
                arrival_datetime = datetime.fromisoformat(leg['arrivalDateTime'])
                departure_date = departure_datetime.date()
                departure_time = departure_datetime.time()
                arrival_time = arrival_datetime.time()
                
                # Get fare
                fare = flight['purchaseLinks'][0]['totalPricePerPassenger']  # Get fare from the first purchase link
                class_of_service = leg['classOfService']
                
                # Insert into database
                cur.execute(insert_query, (
                    source, destination, flight_number, 
                    departure_date, departure_time, 
                    arrival_time, fare, class_of_service
                ))

    # Commit the transaction
    db_conn.commit()

    # Close connection
    cur.close()
    db_conn.close()

    print("Data inserted successfully.")# Store the flight data in the database
    
def store_flight_data(flight_data):
    # Check if there's any flight data
    if not flight_data.get('data', {}).get('flights', []):
        print("No flights data found")
        return "No flights data to store."
    
    conn = psycopg2.connect("dbname=TransitGuide user=postgres password=0000")
    cur = conn.cursor()

    # Create table if it doesn't exist
    create_table_query = """
    CREATE TABLE IF NOT EXISTS IndigoFlights (
        flight_id SERIAL PRIMARY KEY,
        source VARCHAR(10),
        destination VARCHAR(10),
        flight_number INT,
        departure_date DATE,
        departure_time TIME,
        arrival_time TIME,
        fare DECIMAL,
        class VARCHAR(20)
    );
    """
    cur.execute(create_table_query)
    
    insert_query = """
    INSERT INTO IndigoFlights (source, destination, flight_number, departure_date, departure_time, arrival_time, fare, class)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """

    # Insert flight data into the table
    flights = flight_data.get('data', {}).get('flights', [])

    # Debugging: Check if there are any flights to insert
    if not flights:
        print("No flights available for insertion")
    
    for flight in flights:
        for segment in flight['segments']:
            for leg in segment['legs']:
                source = leg['originStationCode']
                destination = leg['destinationStationCode']
                flight_number = leg['flightNumber']
                
                # Convert departure and arrival to separate date and time
                departure_datetime = datetime.fromisoformat(leg['departureDateTime'])
                arrival_datetime = datetime.fromisoformat(leg['arrivalDateTime'])
                departure_date = departure_datetime.date()
                departure_time = departure_datetime.time()
                arrival_time = arrival_datetime.time()
                
                # Get fare
                fare = flight['purchaseLinks'][0]['totalPricePerPassenger']  # Get fare from the first purchase link
                class_of_service = leg['classOfService']
                
                # Debugging: Print each flight's data before inserting
                print(f"Inserting flight: {flight_number}, Source: {source}, Destination: {destination}, Departure: {departure_date} {departure_time}, Arrival: {arrival_time}, Fare: {fare}, Class: {class_of_service}")
                
                # Insert into database
                cur.execute(insert_query, (
                    source, destination, flight_number, 
                    departure_date, departure_time, 
                    arrival_time, fare, class_of_service
                ))

    # Commit the transaction
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    source_city = request.form['source']
    destination_city = request.form['destination']
    journey_date = request.form['date']

    # Get airport codes for the source and destination cities
    source_airport_code = get_airport_code(source_city)
    destination_airport_code = get_airport_code(destination_city)

    if not source_airport_code or not destination_airport_code:
        return "Airport code not found for one or both cities."

    # Fetch flights from API
    fetch_flights(source_airport_code, destination_airport_code, journey_date)

    # # Store the flight data in the database
    # store_flight_data(flight_data)

    return "Flights data has been stored in the database."

if __name__ == '__main__':
    app.run(debug=True)