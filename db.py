import mysql.connector
import os
from dotenv import load_dotenv
from typing import List, Dict, Union
import logging

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        database=os.getenv('DB_NAME'),
        ssl_ca='./DigiCertGlobalRootCA.crt.pem',
        ssl_disabled=False
    )
    print("Connected to database successfully")


def fetch_tenders_by_pincode(pincode: str) -> List[Dict[str, Union[str, int]]]:
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT Tender_ID, pincode, Sanction_Date, Completion_Date, Priorities 
            FROM tendernew
            WHERE pincode = %s
        """
        cursor.execute(query, (pincode,))
        result = cursor.fetchall()
        return result
    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        raise Exception("Database connection or query error")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()