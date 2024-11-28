import psycopg2

def get_globalview_db_connection():
    return psycopg2.connect("dbname=TransitGlobal user=postgres password=0000")
