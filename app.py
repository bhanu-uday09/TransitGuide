from flask import Flask, render_template, request, redirect, flash, jsonify
import psycopg2
import pandas as pd
from fuzzywuzzy import fuzz, process
from fetch_functions import get_airport_code, fetch_air_india_flights, fetch_indigo_flights, fetch_spicejet_flights, data_exists_in_global_flights

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database connection details
DB_NAME = "TransitGlobal"
DB_USER = "postgres"
DB_PASS = "0000"
DB_HOST = "localhost"
DB_PORT = "5432"

# Function to get database connection
def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

# Load the CSV data into a DataFrame
airport_df = pd.read_csv('assets/airport_data.csv', usecols=['city', 'airport_code'])

# Fuzzy Matching for Closest City
def get_closest_city(user_city):
    try:
        city_list = airport_df['city'].tolist()
        result = process.extractOne(user_city.strip().title(), city_list, scorer=fuzz.ratio)

        if result and len(result) >= 2:
            closest_match, score = result
            print(f"Input: {user_city}, Closest Match: {closest_match}, Score: {score}")
            if score >= 50:
                return closest_match
            else:
                print(f"Low match score ({score}) for input: {user_city}")
                return None
        else:
            print(f"No match found for input: {user_city}")
            return None
    except Exception as e:
        print(f"Error finding closest city: {e}")
        return None

# Get Airport Code
def get_airport_code(user_city):
    try:
        closest_city = get_closest_city(user_city)
        if closest_city:
            result = airport_df[airport_df['city'] == closest_city]['airport_code']
            return result.iloc[0] if not result.empty else None
        else:
            print(f"No matching airport code found for city: {user_city}")
            return None
    except Exception as e:
        print(f"Error fetching airport code for {user_city}: {e}")
        return None

# Fetch Airport Code API
@app.route('/api/getAirportCode', methods=['GET'])
def fetch_airport_code():
    user_city = request.args.get('city_name', '')

    if not user_city:
        return jsonify({'error': 'City name is required'}), 400

    try:
        closest_city = get_closest_city(user_city)
        if closest_city:
            result = airport_df[airport_df['city'] == closest_city]
            if not result.empty:
                airport_code = result.iloc[0]['airport_code']
                return jsonify({'city_name': closest_city, 'airport_code': airport_code})
        return jsonify({'error': f'No matching airport code found for "{user_city}"'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Fetch All Flights API
@app.route('/api/all-flights', methods=['GET'])
def get_all_flights():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM global_flights;")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
    return jsonify(data)

# Main Index Route
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            source_city = request.form.get("source_city", "").strip()
            destination_city = request.form.get("destination_city", "").strip()
            journey_date = request.form.get("journey_date", "").strip()

            print(f"Source City: {source_city}, Destination City: {destination_city}, Journey Date: {journey_date}")

            if not source_city or not destination_city or not journey_date:
                flash("All fields are required. Please fill out the form completely.")
                return redirect("/")

            source_code = get_airport_code(source_city)
            destination_code = get_airport_code(destination_city)

            if not source_code or not destination_code:
                flash("Invalid city names. Please check and try again.")
                return redirect("/")

            # Check if data already exists in the global_flights table
            if data_exists_in_global_flights(source_code, destination_code, journey_date):
                flash(f"Flight data for {source_city} to {destination_city} on {journey_date} is already available.")
                return redirect("/results")

            # Fetch data if not already present
            fetch_indigo_flights(source_code, destination_code, journey_date)
            fetch_spicejet_flights(source_code, destination_code, journey_date)
            fetch_air_india_flights(source_code, destination_code, journey_date)

            flash("Flight data fetched and stored successfully!")
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
            print(f"Error during flight data fetching: {str(e)}")
            return redirect("/")
    return render_template("index.html")

# Fetch Flights Based on Criteria
@app.route('/api/flights', methods=['GET'])
def fetch_flights():
    try:
        # Retrieve required query parameters
        source = request.args.get('source_city')
        destination = request.args.get('destination_city')
        journey_date = request.args.get('journey_date')

        # Validate parameters
        if not source or not destination or not journey_date:
            return jsonify({"error": "Missing required parameters"}), 400

        # Database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query to fetch flights, ordered by fare
        query = """
            SELECT flight_number, source_city, destination_city, departure_date, arrival_time, fare, airline
            FROM global_flights
            WHERE source_city = %s AND destination_city = %s AND DATE(departure_date) = %s
            ORDER BY fare ASC
            LIMIT 50;
        """
        cursor.execute(query, (source, destination, journey_date))
        rows = cursor.fetchall()

        # Format query results
        columns = [desc[0] for desc in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify(data)

# Results Page
@app.route('/results', methods=['GET'])
def results():
    source_city = request.args.get('source_city', 'Not Selected')
    destination_city = request.args.get('destination_city', 'Not Selected')
    journey_date = request.args.get('journey_date', 'Not Selected')

    print(f"Source: {source_city}, Destination: {destination_city}, Date: {journey_date}")
    return render_template('results.html', source=source_city, destination=destination_city, date=journey_date)

# Run the App
if __name__ == "__main__":
    app.run(debug=True)