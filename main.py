from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Request
from models import PincodeRequest, ClashResponse, ClashDetails
from db import fetch_tenders_by_pincode
from datetime import datetime
import logging
import asyncio
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This allows all origins (from any domain)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
def root():
    return {"message": "FastAPI service is running!"}

logging.basicConfig(level=logging.DEBUG)

# Define department priorities
DEPARTMENT_PRIORITY = {
    "Department of Water Pipeline": 1,
    "Department of Roadways": 2,
    "Department of Street Lighting": 3
}

def calculate_date_overlap(start1, end1, start2, end2):
    """
    Calculate the number of overlapping days between two date ranges.
    """
    latest_start = max(start1, start2)
    earliest_end = min(end1, end2)
    overlap = (earliest_end - latest_start).days
    return max(0, overlap)

def is_priority_issue(dept1, dept2):
    """
    Determine if a priority issue exists between two departments based on their priority levels.
    """
    return DEPARTMENT_PRIORITY[dept1] < DEPARTMENT_PRIORITY[dept2]

def generate_suggestions(clashes_by_local_area):
    """
    Generate suggestions for resolving clashes based on department priority.
    """
    suggestions = []

    for local_area, clashes in clashes_by_local_area.items():
        # Filter priority clashes and sort them by department priority
        priority_clashes = [
            clash for clash in clashes if clash.priority_issue
        ]
        
        sorted_clashes = sorted(
            priority_clashes,
            key=lambda clash: (
                DEPARTMENT_PRIORITY[clash.department],
                DEPARTMENT_PRIORITY[clash.clashing_department]
            )
        )

        # Generate sequence suggestion
        work_sequence = []
        for clash in sorted_clashes:
            if clash.tender_id not in work_sequence:
                work_sequence.append(clash.tender_id)
            if clash.clashing_tender_id not in work_sequence:
                work_sequence.append(clash.clashing_tender_id)

        if work_sequence:
            suggestions.append(f"In {local_area}, reorder work as follows: {' -> '.join(work_sequence)}.")

    return suggestions

@app.post("/check_clashes", response_model=ClashResponse)
async def check_clashes(request: PincodeRequest):
    try:
        logging.debug(f"Received request for pincode: {request.pincode}")
        tenders = fetch_tenders_by_pincode(request.pincode)
        logging.debug(f"Fetched tenders: {tenders}")

        clashes_by_local_area = {}

        # Iterate through tenders to find clashes grouped by local_area_name
        for tender in tenders:
            for other_tender in tenders:
                if tender["Tender_ID"] != other_tender["Tender_ID"]:
                    # Check if the tenders are in the same area and have date overlap
                    if (
                        tender["area_name"] == other_tender["area_name"] and
                        tender["local_area_name"] == other_tender["local_area_name"]
                    ):
                        overlap_days = calculate_date_overlap(
                            tender["Sanction_Date"], tender["Completion_Date"],
                            other_tender["Sanction_Date"], other_tender["Completion_Date"]
                        )
                        if overlap_days > 0:
                            priority_issue = is_priority_issue(
                                tender["Tender_By_Department"],
                                other_tender["Tender_By_Department"]
                            )

                            # Add to clashes only if there's a priority issue
                            if priority_issue:
                                local_area_clashes = clashes_by_local_area.setdefault(tender["local_area_name"], [])
                                local_area_clashes.append(ClashDetails(
                                    tender_id=tender["Tender_ID"],
                                    clashing_tender_id=other_tender["Tender_ID"],
                                    area_name=tender["area_name"],
                                    local_area_name=tender["local_area_name"],
                                    overlap_days=overlap_days,
                                    priority_issue=priority_issue,
                                    department=tender["Tender_By_Department"],
                                    clashing_department=other_tender["Tender_By_Department"],
                                    tender_start_date=tender["Sanction_Date"].isoformat(),
                                    tender_end_date=tender["Completion_Date"].isoformat(),
                                    clashing_tender_start_date=other_tender["Sanction_Date"].isoformat(),
                                    clashing_tender_end_date=other_tender["Completion_Date"].isoformat()
                                ))

        # Generate suggestions
        suggestions = generate_suggestions(clashes_by_local_area)

        # If no clashes, add a generic suggestion
        if not clashes_by_local_area:
            suggestions.append("No priority clashes detected. No suggestions necessary.")

        return {"clashes_by_local_area": clashes_by_local_area, "suggestions": suggestions}

    except Exception as e:
        logging.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# New PING Endpoint to Receive Pings from Node.js
@app.post("/ping")
async def receive_ping(request: Request):
    try:
        body = await request.json()
        logging.info(f"Received PING from Node.js server: {body}")
        return {"status": "success", "message": "PING received from Node.js server"}
    except Exception as e:
        logging.error(f"Error processing PING request: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing PING request")
    
# Background task for periodic PING to Node.js

async def ping_node_server():
    url = "https://citysynergybackend-jw8z.onrender.com/ping"
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(url)
                logging.info(f"[PING] Node.js server responded: {response.json().get('message', 'Success')}")
            except Exception as e:
                logging.error(f"[PING] Error pinging Node.js server: {str(e)}")
            await asyncio.sleep(600)  # Wait 10 minutes (600 seconds)

# Run the periodic PING task
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(ping_node_server())
