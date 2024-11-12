import psycopg2

def get_indigo_db_connection():
    return psycopg2.connect("dbname=IndiGoDatabase user=postgres password=0000")

def get_spicejet_db_connection():
    return psycopg2.connect("dbname=SpiceJetDatabase user=postgres password=0000")

def get_airindia_db_connection():
    return psycopg2.connect("dbname=AirIndiaDatabase user=postgres password=0000")