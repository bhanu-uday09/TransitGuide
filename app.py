from flask import Flask, render_template, request, redirect, flash, jsonify
import psycopg2
import pandas as pd
from datetime import datetime
from fuzzywuzzy import fuzz, process
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_groq import ChatGroq
from functions import (
    fetch_store_priceline,
    fetch_store_skyscanner,
    fetch_store_train,
    fetch_store_tripadvisor,
    fetch_store_buses
)

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database connection details
DB_NAME = "TransitGlobal"
DB_USER = "postgres"
DB_PASS = "0000"
DB_HOST = "localhost"
DB_PORT = "5432"

REMOTE_DB_NAME = "TrainDB"
REMOTE_DB_USER = "postgres"
REMOTE_DB_PASS = "root"
REMOTE_DB_HOST = "192.168.42.185"
REMOTE_DB_PORT = "5432"

BUS_DB_NAME = "BUS_DATA"
BUS_DB_USER = "postgres"
BUS_DB_PASS = "2301"
BUS_DB_HOST = "192.168.42.113"
BUS_DB_PORT = "5432"

# Database connection functions
def get_db_connection(db_name, db_user, db_pass, db_host, db_port):
    try:
        return psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port
        )
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise

def get_flight_db_connection():
    return get_db_connection(DB_NAME, DB_USER, DB_PASS, DB_HOST, DB_PORT)

def get_train_db_connection():
    return get_db_connection(REMOTE_DB_NAME, REMOTE_DB_USER, REMOTE_DB_PASS, REMOTE_DB_HOST, REMOTE_DB_PORT)

def get_bus_db_connection():
    return get_db_connection(BUS_DB_NAME, BUS_DB_USER, BUS_DB_PASS, BUS_DB_HOST, BUS_DB_PORT)

# Initialize LLM
llm = ChatGroq(
    temperature=0,
    groq_api_key='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',
    model_name="llama-3.1-70b-versatile"
)

# Initialize memory
memory = ConversationBufferMemory()

# Create Chatbot
travel_chatbot = ConversationChain(llm=llm, memory=memory)

# Define Travel-Related Filter
def is_travel_related(query):
    travel_keywords = [
        "flight", "hotel", "train", "bus",
        "accommodation", "trip", "destination",
        "visa", "itinerary"
    ]
    return any(keyword in query.lower() for keyword in travel_keywords)

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        user_input = request.json.get("message", "")
        if not user_input:
            return jsonify({"response": "Please provide a valid input."}), 400

        if is_travel_related(user_input):
            try:
                response = travel_chatbot.invoke({"input": user_input})
                return jsonify({"response": response.get("response", "No response available")}), 200
            except Exception as e:
                print(f"Error in chatbot route: {e}")
                return jsonify({"response": "An error occurred while processing your request."}), 500
        else:
            return jsonify({"response": "I can only assist with travel-related queries like flights, hotels, or itineraries."}), 400

    return render_template("chatbot.html")

# Load airport data
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code', 'railway_station_code'])

def get_close_city(user_city):
    city_list = airport_df['city'].tolist()
    result = process.extractOne(user_city.strip().title(), city_list, scorer=fuzz.ratio)
    return result[0] if result and result[1] >= 50 else None

@app.route('/api/getClosestCity', methods=['GET'])
def get_closest_city():
    """
    Returns the closest matching city name from a predefined list based on a user's input city.
    """
    # Extract the 'user_city' parameter from the query string
    user_city = request.args.get('user_city', '').strip().title()

    if not user_city:
        return jsonify({"error": "user_city parameter is required"}), 400

    # Get the list of cities from the dataframe
    city_list = airport_df['city'].tolist()

    # Perform fuzzy matching
    result = process.extractOne(user_city, city_list, scorer=fuzz.ratio)

    # Check if a result was found and the score is acceptable
    if result and result[1] >= 50:
        return jsonify({"closest_city": result[0]}), 200
    else:
        return jsonify({"error": "No closely matching city found"}), 404
    
def get_airport_code(user_city):
    closest_city = get_close_city(user_city)
    if closest_city:
        result = airport_df[airport_df['city'] == closest_city]['airport_code']
        return result.iloc[0] if not result.empty else None
    return None

def get_railway_station_code(user_city):
    closest_city = get_close_city(user_city)
    if closest_city:
        result = airport_df[airport_df['city'] == closest_city]['railway_station_code']
        return result.iloc[0] if not result.empty else None
    return None

@app.route('/api/getAirportCode', methods=['GET'])
def fetch_airport_code():
    user_city = request.args.get('city_name', '')
    if not user_city:
        return jsonify({'error': 'City name is required'}), 400

    airport_code = get_airport_code(user_city)
    if airport_code:
        return jsonify({'city_name': user_city, 'airport_code': airport_code}), 200
    return jsonify({'error': f'No matching airport code found for "{user_city}"'}), 404

@app.route('/api/getRailwayStationCode', methods=['GET'])
def fetch_railway_station_code():
    user_city = request.args.get('city_name', '')
    if not user_city:
        return jsonify({'error': 'City name is required'}), 400

    station_code = get_railway_station_code(user_city)
    if station_code:
        return jsonify({'city_name': user_city, 'railway_station_code': station_code}), 200
    return jsonify({'error': f'No matching railway station code found for "{user_city}"'}), 404

# Function to get the city name from the airport code
def get_city_from_airport_code(airport_code):
    result = airport_df[airport_df['airport_code'] == airport_code]['city']
    return result.iloc[0] if not result.empty else None

@app.route('/api/getCityFromAirportCode', methods=['GET'])
def fetch_city_from_airport_code():
    airport_code = request.args.get('airport_code', '').strip().upper()
    if not airport_code:
        return jsonify({'error': 'Airport code is required'}), 400

    city_name = get_city_from_airport_code(airport_code)
    if city_name:
        return jsonify({'airport_code': airport_code, 'city_name': city_name}), 200
    return jsonify({'error': f'No matching city found for airport code "{airport_code}"'}), 404

@app.route('/api/flights', methods=['GET'])
def fetch_flights():
    source = request.args.get('source_city', '').strip()
    destination = request.args.get('destination_city', '').strip()
    journey_date = request.args.get('journey_date', '').strip()

    if not source or not destination or not journey_date:
        return jsonify({"error": "Source city, destination city, and journey date are required"}), 400

    try:
        with get_flight_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT flight_id, source_city, destination_city, departure_timestamp,
                        arrival_timestamp, fare, airline
                    FROM global_flights
                    WHERE source_city = %s AND destination_city = %s AND DATE(departure_timestamp) = %s
                    ORDER BY departure_timestamp ASC
                    LIMIT 50;
                """
                cursor.execute(query, (source, destination, journey_date))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]
        return jsonify(data), 200
    except Exception as e:
        print(f"Error fetching flights: {e}")
        return jsonify({"error": "An error occurred while fetching flight data."}), 500

@app.route('/api/buses', methods=['GET'])
def fetch_buses():
    source = request.args.get('source_city', '').strip()
    destination = request.args.get('destination_city', '').strip()
    journey_date = request.args.get('journey_date', '').strip()

    if not source or not destination or not journey_date:
        return jsonify({"error": "Source city, destination city, and journey date are required"}), 400

    try:
        with get_bus_db_connection() as conn:  # Use a function to get the bus database connection
            with conn.cursor() as cursor:
                query = """
                    SELECT id AS bus_id, source_city, destination_city, departure_time,
                        arrival_time, total_travel_time, fare, bus_type
                    FROM buses
                    WHERE source_city = %s AND destination_city = %s AND DATE(departure_time) = %s
                    ORDER BY departure_time ASC
                    LIMIT 50;
                """
                cursor.execute(query, (source, destination, journey_date))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]
        return jsonify(data), 200
    except Exception as e:
        print(f"Error fetching buses: {e}")
        return jsonify({"error": "An error occurred while fetching bus data."}), 500

@app.route('/api/getTrainData', methods=['GET'])
def get_train_data():
    """
    Fetch train data for a given source, destination, and travel date.
    If data is not found in PostgreSQL, fetch it from the external API, save to MongoDB,
    and then transfer to PostgreSQL.
    """
    source = request.args.get('source', '').strip().upper()
    destination = request.args.get('destination', '').strip().upper()
    travel_date = request.args.get('date', '').strip()

    if not all([source, destination, travel_date]):
        return jsonify({"error": "Source, destination, and travel date are required"}), 400

    try:
        # Check if data exists in PostgreSQL
        with get_train_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT train_number, train_name, source_station_code, source_city,
                           destination_station_code, destination_city, departure_date, arrival_date,
                           departure_time::TEXT AS departure_time, departure_day, 
                           arrival_time::TEXT AS arrival_time, arrival_day, travel_duration, ticket_prices
                    FROM TrainDetails
                    WHERE source_station_code = %s
                      AND destination_station_code = %s
                      AND departure_date = %s
                """
                cursor.execute(query, (source, destination, travel_date))
                rows = cursor.fetchall()

                if rows:
                    # Data found in PostgreSQL
                    columns = [desc[0] for desc in cursor.description]
                    data = [dict(zip(columns, row)) for row in rows]
                    return jsonify({"train_data": data}), 200

        # If no data found in PostgreSQL, fetch from external API
        formatted_date = datetime.strptime(travel_date, "%Y-%m-%d").strftime("%Y%m%d")
        train_details = fetch_store_train.fetch_train_details(source, destination, formatted_date)
        fetch_store_train.transfer_data_to_postgres()

        if not train_details:
            return jsonify({"error": "No train details found for the given parameters"}), 404

        # Transfer data to MongoDB
        collection = fetch_store_train.get_mongo_connection()
        if collection is not None:
            collection.insert_many(train_details)
            print(f"Inserted {len(train_details)} records into MongoDB.")

        # Transfer data from MongoDB to PostgreSQL
        fetch_store_train.transfer_data_to_postgres()

        # Fetch data from PostgreSQL to return to the user
        with get_train_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (source, destination, travel_date))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]

        return jsonify({"train_data": data}), 200

    except Exception as e:
        print(f"Error fetching train data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        source_city = request.form.get("source_city", "").strip()
        src_air_code = get_airport_code(source_city)
        sc_stn_code = get_railway_station_code(source_city)
        destination_city = request.form.get("destination_city", "").strip()
        dst_air_code = get_airport_code(destination_city)
        dst_stn_code = get_railway_station_code(destination_city)
        journey_date = request.form.get("journey_date", "").strip()
        

        if not source_city or not destination_city or not journey_date:
            flash("All fields are required. Please fill out the form completely.")
            return redirect("/")

        if not src_air_code or not dst_air_code:
            flash("Invalid city names. Please check and try again.")
            return redirect("/")

        if get_matching_flights(src_air_code, dst_air_code, journey_date):
            flash(f"Flight data for {source_city} to {destination_city} on {journey_date} is already available.")
            return redirect("/results")

        if get_matching_trains(sc_stn_code, dst_stn_code, journey_date):
            flash(f"Train data for {source_city} to {destination_city} on {journey_date} is already available.")
            return redirect("/results")
        
        if get_matching_buses(source_city, destination_city, journey_date):
            flash(f"Train data for {source_city} to {destination_city} on {journey_date} is already available.")
            return redirect("/results")
        
        try:
            fetch_store_train.fetch_train_details(sc_stn_code, dst_stn_code, journey_date)
            fetch_store_buses.fetch_and_insert_bus_data(source_city, destination_city, journey_date)
            fetch_store_priceline.get_priceline_flights(src_air_code, dst_air_code, journey_date)
            fetch_store_skyscanner.get_skyScanner_flights(src_air_code, dst_air_code, journey_date)
            fetch_store_tripadvisor.get_tripadvisor_flights(src_air_code, dst_air_code, journey_date)
            flash("Flight and train data fetched successfully!")
        except Exception as e:
            flash(f"An error occurred while fetching data: {str(e)}")
            return redirect("/")
    return render_template("index.html")

@app.route('/results', methods=['GET'])
def results():
    source_city = request.args.get('source_city', 'Not Selected')
    destination_city = request.args.get('destination_city', 'Not Selected')
    journey_date = request.args.get('journey_date', 'Not Selected')
    return render_template('results.html', source=source_city, destination=destination_city, date=journey_date)

def get_matching_flights(source_code, destination_code, journey_date):
    """
    Fetch all matching flight data from the global_flights table for the given parameters.

    Args:
        source_code (str): The source airport code.
        destination_code (str): The destination airport code.
        journey_date (str): The journey date in YYYY-MM-DD format.

    Returns:
        list: A list of dictionaries representing the flight data. Returns an empty list if no flights are found.
    """
    try:
        with get_flight_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT flight_id, source_city, destination_city, 
                           departure_timestamp, arrival_timestamp, fare, airline
                    FROM global_flights
                    WHERE source_city = %s
                    AND destination_city = %s
                    AND DATE(departure_timestamp) = %s
                    ORDER BY fare ASC;
                """
                cursor.execute(query, (source_code, destination_code, journey_date))
                rows = cursor.fetchall()

                # Convert rows to a list of dictionaries
                columns = [desc[0] for desc in cursor.description]
                flights = [dict(zip(columns, row)) for row in rows]

                return flights
    except Exception as e:
        print(f"Error fetching flight data from database: {e}")
        return []

def get_matching_trains(source_station_code, destination_station_code, travel_date):
    """
    Retrieve a list of trains for the given source, destination, and travel date.
    """
    try:
        # Connect to the database
        with get_train_db_connection() as conn:
            with conn.cursor() as cursor:
                # Query to fetch train details
                query = """
                    SELECT train_number, train_name, source_station_code, source_city,
                           destination_station_code, destination_city, travel_date, ticket_prices
                    FROM TrainDetails
                    WHERE source_station_code = %s
                      AND destination_station_code = %s
                      AND travel_date = %s
                """
                cursor.execute(query, (source_station_code, destination_station_code, travel_date))
                rows = cursor.fetchall()

                # Get column names for creating a dictionary
                columns = [desc[0] for desc in cursor.description]

                # Return the list of trains as dictionaries
                return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"Error retrieving train data: {e}")
        return []

def get_matching_buses(source_city, destination_city, journey_date):
    """
    Fetch all matching bus data from the buses table for the given parameters.

    Args:
        source_city (str): The source city.
        destination_city (str): The destination city.
        journey_date (str): The journey date in YYYY-MM-DD format.

    Returns:
        list: A list of dictionaries representing the bus data. Returns an empty list if no buses are found.
    """
    try:
        with get_bus_db_connection() as conn:  # Use a function to get the bus database connection
            with conn.cursor() as cursor:
                query = """
                    SELECT id AS bus_id, source_city, destination_city, 
                           departure_time, arrival_time, fare, bus_type
                    FROM buses
                    WHERE source_city = %s
                    AND destination_city = %s
                    AND DATE(departure_time) = %s
                    ORDER BY fare ASC;
                """
                cursor.execute(query, (source_city, destination_city, journey_date))
                rows = cursor.fetchall()

                # Convert rows to a list of dictionaries
                columns = [desc[0] for desc in cursor.description]
                buses = [dict(zip(columns, row)) for row in rows]

                return buses
    except Exception as e:
        print(f"Error fetching bus data from database: {e}")
        return []

if __name__ == "__main__":
    app.run(debug=True)