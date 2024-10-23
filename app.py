from flask import Flask, render_template, request, redirect, flash
from fetch_functions import (
    fetch_indigo_flights,
    fetch_spicejet_flights,
    fetch_air_india_flights,
    get_airport_code
)

app = Flask(__name__)
app.secret_key = "your_secret_key"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Print the incoming data for debugging
        print(f"Source City: {request.form['source_city']}")
        print(f"Destination City: {request.form['destination_city']}")
        print(f"Journey Date: {request.form['journey_date']}")

        # Get the user input
        source_city = request.form["source_city"]
        destination_city = request.form["destination_city"]
        journey_date = request.form["journey_date"]

        # Fetch airport codes
        source_code = get_airport_code(source_city)
        destination_code = get_airport_code(destination_city)

        # Check if airport codes are valid
        if not source_code or not destination_code:
            flash("Invalid city names. Please try again.")
            return redirect("/")

        # Call the flight fetching functions
        try:
            fetch_indigo_flights(source_code, destination_code, journey_date)
            fetch_spicejet_flights(source_code, destination_code, journey_date)
            fetch_air_india_flights(source_code, destination_code, journey_date)
            flash("Flight data fetched and stored successfully!")
        except Exception as e:
            flash(f"Error: {str(e)}")
            print(f"Error occurred: {str(e)}")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)