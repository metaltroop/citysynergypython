# main.py
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from models import PincodeRequest, ClashResponse, ClashDetails
from db import fetch_tenders_by_pincode
from datetime import datetime
import logging

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

def calculate_date_overlap(start1, end1, start2, end2):
    # Calculate overlapping days
    latest_start = max(start1, start2)
    earliest_end = min(end1, end2)
    overlap = (earliest_end - latest_start).days
    return max(0, overlap)

def is_priority_issue(dept1, dept2):
    # Define priority order: Water Pipeline > Roadways > Street Lighting
    priority_order = ["Water Supply and Sewerage Board", "Urban Transport Planning Authorities", "Electricity Department"]
    return priority_order.index(dept1) > priority_order.index(dept2)

@app.post("/check_clashes", response_model=ClashResponse)
async def check_clashes(request: PincodeRequest):
    try:
        logging.debug(f"Received request for pincode: {request.pincode}")
        tenders = fetch_tenders_by_pincode(request.pincode)
        logging.debug(f"Fetched tenders: {tenders}")

        clashes = []
        # Iterate through each pair of tenders to find clashes
        for tender in tenders:
            for other_tender in tenders:
                if tender["Tender_ID"] != other_tender["Tender_ID"]:
                    # Check if the tenders are in the same area and local area
                    if (
                        tender["area_name"] == other_tender["area_name"] and
                        tender["local_area_name"] == other_tender["local_area_name"]
                    ):
                        overlap_days = calculate_date_overlap(
                            tender["Sanction_Date"], tender["Completion_Date"],
                            other_tender["Sanction_Date"], other_tender["Completion_Date"]
                        )
                        if overlap_days > 0:
                            priority_issue = is_priority_issue(tender["Tender_By_Department"], other_tender["Tender_By_Department"])
                            # Only add the clash to the list if there's a priority issue
                            if priority_issue:
                                clashes.append(ClashDetails(
                                    tender_id=tender["Tender_ID"],
                                    clashing_tender_id=other_tender["Tender_ID"],
                                    overlap_days=overlap_days,
                                    priority_issue=priority_issue,
                                    department=tender["Tender_By_Department"],
                                    clashing_department=other_tender["Tender_By_Department"],
                                    tender_start_date=tender["Sanction_Date"].isoformat(),
                                    tender_end_date=tender["Completion_Date"].isoformat(),
                                    clashing_tender_start_date=other_tender["Sanction_Date"].isoformat(),
                                    clashing_tender_end_date=other_tender["Completion_Date"].isoformat()
                                ))

        logging.debug(f"Detected clashes with priority issues: {clashes}")

        suggestions = []
        # Only generate suggestions for clashes that have a priority issue
        for clash in clashes:
            if clash.priority_issue:
                suggestions.append(
                    f"Reorder work: {clash.clashing_tender_id} should precede {clash.tender_id} based on department priority."
                )

        # If there are no priority clashes, we can return an empty suggestions list
        if not clashes:
            suggestions.append("No priority clashes detected. No suggestions necessary.")

        return {"clashes": clashes, "suggestions": suggestions}
    
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))
