from fastapi import FastAPI, HTTPException
from models import PincodeRequest, ClashResponse, ClashDetails
from db import fetch_tenders_by_pincode
from datetime import datetime, date
import logging

app = FastAPI()
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
    # Define priority order
    priority_order = ["Department of Water Pipeline", "Department of Roadways", "Department of Street Lighting"]
    return priority_order.index(dept1) > priority_order.index(dept2)

@app.post("/check_clashes", response_model=ClashResponse)
async def check_clashes(request: PincodeRequest):
    try:
        logging.debug(f"Received request for pincode: {request.pincode}")
        tenders = fetch_tenders_by_pincode(request.pincode)
        logging.debug(f"Fetched tenders: {tenders}")

        clashes = []
        for tender in tenders:
            for other_tender in tenders:
                if tender["Tender_ID"] != other_tender["Tender_ID"]:
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
                            clashes.append(ClashDetails(
                                tender_id=tender["Tender_ID"],
                                clashing_tender_id=other_tender["Tender_ID"],
                                overlap_days=overlap_days,
                                priority_issue=priority_issue
                            ))

        logging.debug(f"Detected clashes: {clashes}")

        suggestions = []
        for clash in clashes:
            if clash.priority_issue:
                suggestions.append(
                    f"Reorder work: {clash.clashing_tender_id} should precede {clash.tender_id} based on department priority."
                )

        return {"clashes": clashes, "suggestions": suggestions}
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))
