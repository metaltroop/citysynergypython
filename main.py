# main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime, date
from typing import List, Dict, Union

load_dotenv()

app = FastAPI()

class PincodeRequest(BaseModel):
    pincode: str

def fetch_data_from_db(pincode: str) -> List[Dict[str, Union[str, int]]]:
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            database=os.getenv('DB_NAME'),
            ssl_ca='./DigiCertGlobalRootCA.crt.pem',
            ssl_disabled=False
        )
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT Tender_ID, pincode, Sanction_Date, Completion_Date, Priorities 
            FROM tenders 
            WHERE pincode = %s
        """
        cursor.execute(query, (pincode,))
        result = cursor.fetchall()
        return result
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database error: {err}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

@app.post("/check_clashes")
async def check_clashes(request: PincodeRequest):
    data = fetch_data_from_db(request.pincode)

    # Convert date fields to ISO format
    for row in data:
        if isinstance(row['Sanction_Date'], (datetime, date)):
            row['Sanction_Date'] = row['Sanction_Date'].isoformat()
        if isinstance(row['Completion_Date'], (datetime, date)):
            row['Completion_Date'] = row['Completion_Date'].isoformat()

    return {"clashes": data}
