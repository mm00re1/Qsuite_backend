import asyncio
import json
import logging
from queue import Empty
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from KdbSubs import *
from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session

from models.models import TestGroup
from dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

def make_json_serializable(data):
    """Recursively convert non-serializable objects in the data to JSON-friendly types."""
    if isinstance(data, dict):
        # Convert each value in the dictionary
        return {key: make_json_serializable(value) for key, value in data.items()}
    elif isinstance(data, list):
        # Convert each element in the list
        return [make_json_serializable(element) for element in data]
    elif isinstance(data, pd.Timedelta):
        # Convert Timedelta to string (or seconds if you prefer)
        return str(data).split(" ")[-1]
    elif hasattr(data, 'item'):  # Handles numpy types like np.int32, np.float64
        return data.item()
    else:
        return data

@router.get("/search_functional_tests/")
async def search_functional_tests(
    query: str,
    limit: int = 10,
    group_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    try:
        matchingTestNames = sendKdbQuery('.qsuite.showMatchingTests', test_group.server, test_group.port, test_group.tls, query)
        matchingTestNames = matchingTestNames[:limit]
        results = [x.decode('latin') for x in matchingTestNames]
        return {"success": True, "results": results, "message": ""}
    except Exception as e:
        return {"success": False, "results": [], "message": "Kdb Error while searching for matching q function => " + str(e)}

@router.websocket("/live")
async def trade_sub_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    # Example the client can connect with: ws://localhost:8000/live?tbl=trade&index=TSLA
    await websocket.accept()

    # Extract query params from the WebSocket URL
    raw_group_id = websocket.query_params.get('group_id')
    sub_name = websocket.query_params.get('sub_name')

    try:
        group_id = UUID(raw_group_id)
    except ValueError:
        await websocket.send_text(f"Invalid group_id: {raw_group_id}")
        await websocket.close()
        return

    test_group = db.query(TestGroup).filter(TestGroup.id == group_id.bytes).first()

    if not test_group:
        await websocket.send_text("TestGroup not found.")
        await websocket.close()
        return

    kdb_host = test_group.server
    kdb_port = test_group.port
    kdb_tls = test_group.tls

    # Collect up to 8 generic params from query string
    extra_params = []
    for i in range(1, 9):  # 1 through 8
        val = websocket.query_params.get(f'param{i}')
        if val is not None:
            extra_params.append(val)

    # Create the subscription thread with *args
    qThread = kdbSub(sub_name, kdb_host, kdb_port, kdb_tls, *extra_params)
    qThread.start()

    keepalive_counter = 0

    try:
        while True:
            if qThread.stopped():
                break

            try:
                # Attempt to get data without blocking:
                data = qThread.message_queue.get_nowait()
            except Empty:
                data = None

            if data:
                # The structure of your data depends on how your Q subscription
                # handles the sub_name + args. Let's do a generic forward:
                try:
                    # Convert numpy types to Python native types (e.g., int, float)
                    print("raw data: ", data)
                    serializable_data = make_json_serializable(data)
                    json_data = json.dumps(serializable_data)
                    await websocket.send_text(json_data)
                except Exception as e:
                    # Log any unexpected serialization errors
                    logger.exception(f"Error serializing data: {e}")

            else:
                keepalive_counter += 1
                if keepalive_counter >= 100:  # e.g. every ~1 second if each loop is 0.01s
                    # Force a send that fails if the socket is closed
                    await websocket.send_text("KEEPALIVE")
                    keepalive_counter = 0

                # Yield control back to the event loop briefly
                await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
    except Exception as e:
        print(f"Unhandled WebSocket error: {e}")
    finally:
        # Clean up the subscription thread
        qThread.stopit()
        print("finished the stopit")

