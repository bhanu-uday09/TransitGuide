from flask import Flask, render_template, request, redirect, flash
from fetch_functions import get_airport_code, fetch_air_india_flights, fetch_indigo_flights, fetch_spicejet_flights

app = Flask(__name__)
app.secret_key = "your_secret_key"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # Fetch and log user input
            source_city = request.form.get("source_city", "").strip()
            destination_city = request.form.get("destination_city", "").strip()
            journey_date = request.form.get("journey_date", "").strip()
            
            print(f"Source City: {source_city}")
            print(f"Destination City: {destination_city}")
            print(f"Journey Date: {journey_date}")

            # Validate input
            if not source_city or not destination_city or not journey_date:
                flash("All fields are required. Please fill out the form completely.")
                return redirect("/")

            # Fetch airport codes
            source_code = get_airport_code(source_city)
            destination_code = get_airport_code(destination_city)

            if not source_code or not destination_code:
                flash("Invalid city names. Please check and try again.")
                return redirect("/")

            # Fetch flight data
            fetch_indigo_flights(source_code, destination_code, journey_date)
            fetch_spicejet_flights(source_code, destination_code, journey_date)
            fetch_air_india_flights(source_code, destination_code, journey_date)

            flash("Flight data fetched and stored successfully!")
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
            print(f"Error during flight data fetching: {str(e)}")
            return redirect("/")
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)