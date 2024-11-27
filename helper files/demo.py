from flask import Flask, render_template, request, redirect, flash, jsonify
import psycopg2
import pandas as pd
from datetime import datetime 
from fuzzywuzzy import fuzz, process
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_groq import ChatGroq
from fetch_functions import get_airport_code, fetch_air_india_flights, fetch_indigo_flights, fetch_spicejet_flights, data_exists_in_global_flights
from train_functions import fetch_train_data, create_postgres_table, insert_data_to_postgres

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database connection details
DB_NAME = "TransitGlobal"
DB_USER = "postgres"
DB_PASS = "0000"
DB_HOST = "localhost"
DB_PORT = "5432"

REMOTE_DB_NAME = "Train_Database"
REMOTE_DB_USER = "postgres"
REMOTE_DB_PASS = "root"
REMOTE_DB_HOST = "192.168.42.185"
REMOTE_DB_PORT = "5432"

BUS_DB_NAME = "BUS_DATA"
BUS_DB_USER = "postgres"
BUS_DB_PASS = "2301"
BUS_DB_HOST = "192.168.42.113"
BUS_DB_PORT = "5432"

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
    travel_keywords = ["flight", "hotel", "train", "bus", "accommodation", "trip", "destination", "visa", "itinerary"]
    return any(keyword in query.lower() for keyword in travel_keywords)

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        try:
            # Get the user's message from the request
            user_input = request.json.get("message", "")
            if not user_input:
                return jsonify({"response": "Please provide a valid input."}), 400

            # Check if the query is travel-related
            if is_travel_related(user_input):
                # Get the response from the chatbot
                response = travel_chatbot.invoke({"input": user_input})
                print("Chatbot Response:", response)  # Debug print
                # Return the bot's response field if available
                return jsonify({"response": response.get("response", "No response available")})
            else:
                return jsonify({"response": "I can only assist with travel-related queries like flights, hotels, or itineraries."})

        except Exception as e:
            # Log the exception and return an error response
            print(f"Error in chatbot route: {e}")
            return jsonify({"response": "An error occurred while processing your request. Please try again."}), 500

    # For GET requests, render the chatbot HTML page
    return render_template("chatbot.html")

# Database connection functions
def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

def get_remote_db_connection():
    return psycopg2.connect(
        dbname=REMOTE_DB_NAME,
        user=REMOTE_DB_USER,
        password=REMOTE_DB_PASS,
        host=REMOTE_DB_HOST,
        port=REMOTE_DB_PORT
    )

def get_bus_db_connection():
    return psycopg2.connect(
        dbname=BUS_DB_NAME,
        user=BUS_DB_USER,
        password=BUS_DB_PASS,
        host=BUS_DB_HOST,
        port=BUS_DB_PORT
    )
    
    
@app.route('/api/get_bus_fares', methods=['GET'])
def fetch_bus_fares():
    try:
        # Get source_city and destination_city from the request
        source_city = request.args.get('source_city', '').strip()
        destination_city = request.args.get('destination_city', '').strip()

        # Validate inputs
        if not source_city or not destination_city:
            return jsonify({'error': 'Both source and destination cities are required'}), 400

        print(f"Fetching bus fares for Source City: {source_city}, Destination City: {destination_city}")

        # Query the bus_fares table filtering by source_city and destination_city
        with get_bus_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT source, destination, fare_range
                    FROM bus_fares
                    WHERE source = %s AND destination = %s;
                """
                cursor.execute(query, (source_city, destination_city))
                rows = cursor.fetchall()

                # Define column names for the result
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]

        # Check if no data was found
        if not data:
            return jsonify({'message': 'No bus fare data found for the selected route'}), 404

        # Return the fetched data
        return jsonify(data), 200

    except Exception as e:
        # Log the error and return a 500 response
        print(f"Error fetching bus fare data: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500
    
    
# Load airport data
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code'])

# Fuzzy matching for city names
def get_closest_city(user_city):
    city_list = airport_df['city'].tolist()
    result = process.extractOne(user_city.strip().title(), city_list, scorer=fuzz.ratio)
    if result and result[1] >= 50:
        return result[0]
    return None

def get_airport_code(user_city):
    closest_city = get_closest_city(user_city)
    if closest_city:
        result = airport_df[airport_df['city'] == closest_city]['airport_code']
        return result.iloc[0] if not result.empty else None
    return None

# API to fetch airport code
@app.route('/api/getAirportCode', methods=['GET'])
def fetch_airport_code():
    user_city = request.args.get('city_name', '')
    if not user_city:
        return jsonify({'error': 'City name is required'}), 400
    airport_code = get_airport_code(user_city)
    if airport_code:
        return jsonify({'city_name': user_city, 'airport_code': airport_code}), 200
    return jsonify({'error': f'No matching airport code found for "{user_city}"'}), 404

# API to fetch all flights
@app.route('/api/all-flights', methods=['GET'])
def get_all_flights():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM global_flights;")
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API to fetch train data
@app.route('/api/get_train_data', methods=['GET'])
def fetch_train_data():
    try:
        with get_remote_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM train_data;')
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                data = [dict(zip(columns, row)) for row in rows]
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Main index route
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        source_city = request.form.get("source_city", "").strip()
        destination_city = request.form.get("destination_city", "").strip()
        journey_date = request.form.get("journey_date", "").strip()

        if not source_city or not destination_city or not journey_date:
            flash("All fields are required. Please fill out the form completely.")
            return redirect("/")

        source_code = get_airport_code(source_city)
        destination_code = get_airport_code(destination_city)

        if not source_code or not destination_code:
            flash("Invalid city names. Please check and try again.")
            return redirect("/")

        if data_exists_in_global_flights(source_code, destination_code, journey_date):
            flash(f"Flight data for {source_city} to {destination_city} on {journey_date} is already available.")
            return redirect("/results")

        try:
            fetch_indigo_flights(source_code, destination_code, journey_date)
            fetch_spicejet_flights(source_code, destination_code, journey_date)
            fetch_air_india_flights(source_code, destination_code, journey_date)
            flash("Flight data fetched and stored successfully!")
        except Exception as e:
            flash(f"An error occurred while fetching flight data: {str(e)}")
            return redirect("/")
    return render_template("index.html")

# API to fetch flights by criteria
@app.route('/api/flights', methods=['GET'])
def fetch_flights():
    source = request.args.get('source_city')
    destination = request.args.get('destination_city')
    journey_date = request.args.get('journey_date')

    if not source or not destination or not journey_date:
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT flight_number, source_city, destination_city, departure_date, arrival_time, fare, airline
                    FROM global_flights
                    WHERE source_city = %s AND destination_city = %s AND DATE(departure_date) = %s
                    ORDER BY fare ASC
                    LIMIT 50;
                """
                cursor.execute(query, (source, destination, journey_date))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Results page
@app.route('/results', methods=['GET'])
def results():
    source_city = request.args.get('source_city', 'Not Selected')
    destination_city = request.args.get('destination_city', 'Not Selected')
    journey_date = request.args.get('journey_date', 'Not Selected')
    return render_template('results.html', source=source_city, destination=destination_city, date=journey_date)

# Run the app
if __name__ == "__main__":
    app.run(debug=True)