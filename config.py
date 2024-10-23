import psycopg2

def get_db_connection():
    return psycopg2.connect("dbname=TransitGuide user=postgres password=0000")