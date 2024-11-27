import psycopg2

def get_skyscanner_db_connection():
    return psycopg2.connect("dbname=SkyScannerDB user=postgres password=0000")

def get_priceline_db_connection():
    return psycopg2.connect("dbname=PriceLineDB user=postgres password=0000")

def get_tripadvisor_db_connection():
    return psycopg2.connect("dbname=TripAdvisorDB user=postgres password=0000")

def get_globalview_db_connection():
    return psycopg2.connect("dbname=TransitGlobal user=postgres password=0000")