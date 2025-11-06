"""
WebSocket Router
Handles all real-time WebSocket endpoints for streaming updates
"""
import logging
import asyncio
from typing import Optional, Callable, Any
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.websocket_manager import ConnectionType
from db.mdb import MongoDBConnector

logger = logging.getLogger(__name__)

# Note: WebSocket routes don't use a standard prefix
# Each endpoint will be registered at its full path (/ws/alerts, /ws/sensors, /ws/wafers)
router = APIRouter(
    tags=["WebSockets"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (injected from main.py on startup)
ws_manager_instance = None
mongodb_connector_class: type[MongoDBConnector] | None = None
convert_objectids_func: Callable | None = None
mdb_uri: str | None = None
mdb_database_name: str | None = None


def set_dependencies(
    ws_manager,
    connector_class: type[MongoDBConnector],
    convert_func: Callable,
    uri: str,
    db_name: str
):
    """
    Inject dependencies from main.py
    
    Args:
        ws_manager: WebSocketManager instance for managing connections
        connector_class: MongoDBConnector class for sync database operations
        convert_func: Utility function to convert ObjectIds to strings
        uri: MongoDB connection URI
        db_name: MongoDB database name
    """
    global ws_manager_instance, mongodb_connector_class
    global convert_objectids_func, mdb_uri, mdb_database_name
    
    ws_manager_instance = ws_manager
    mongodb_connector_class = connector_class
    convert_objectids_func = convert_func
    mdb_uri = uri
    mdb_database_name = db_name
    
    logger.info("✅ WebSocket dependencies injected into router")


def get_mongodb_connector() -> MongoDBConnector:
    """Get MongoDB connector with error handling"""
    if mongodb_connector_class is None or mdb_uri is None or mdb_database_name is None:
        logger.error("❌ MongoDB connector not initialized")
        raise RuntimeError("Database connection not initialized")
    return mongodb_connector_class(uri=mdb_uri, database_name=mdb_database_name)


def convert_objectids(data: Any) -> Any:
    """Convert ObjectIds in data using injected function"""
    if convert_objectids_func is None:
        logger.error("❌ ObjectId conversion function not injected")
        raise RuntimeError("ObjectId conversion function not available")
    return convert_objectids_func(data)


logger.info("📦 WebSocket router initialized")


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert updates
    """
    # Validate dependencies
    if ws_manager_instance is None:
        logger.error("❌ WebSocket /ws/alerts - ws_manager not initialized")
        await websocket.close(code=1011, reason="Server not initialized")
        return
    
    # Connect with WebSocket manager
    client_id = await ws_manager_instance.connect(
        websocket=websocket,
        connection_type=ConnectionType.ALERTS
    )
    
    logger.info(f"🔌 WebSocket /ws/alerts - Client {client_id} connected")
    logger.debug(f"⚙️ Using connection type: {ConnectionType.ALERTS}")

    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            logger.debug(f"📥 Message from {client_id}: {data[:50]}..." if len(data) > 50 else f"📥 Message from {client_id}: {data}")

            # Handle client messages (subscriptions, filters, etc.)
            await ws_manager_instance.handle_client_message(client_id, data)

    except WebSocketDisconnect:
        await ws_manager_instance.disconnect(client_id)
        logger.info(f"🔌 WebSocket /ws/alerts - Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"❌ WebSocket /ws/alerts - Error for {client_id}: {e}", exc_info=True)
        await ws_manager_instance.disconnect(client_id)


@router.websocket("/ws/sensors")
async def websocket_sensors(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sensor data streaming with periodic updates
    """
    # Validate dependencies
    if ws_manager_instance is None:
        logger.error("❌ WebSocket /ws/sensors - ws_manager not initialized")
        await websocket.close(code=1011, reason="Server not initialized")
        return
    
    # Connect with WebSocket manager
    client_id = await ws_manager_instance.connect(
        websocket=websocket,
        connection_type=ConnectionType.SENSORS
    )
    
    logger.info(f"🔌 WebSocket /ws/sensors - Client {client_id} connected")
    logger.debug(f"⚙️ Using connection type: {ConnectionType.SENSORS}")

    try:
        with get_mongodb_connector() as mdb_connector:
            sensor_collection = mdb_connector.get_collection("sensor_events")  # Use real-time collection
            last_update_time = datetime.utcnow()
            logger.debug(f"⚙️ MongoDB connector established for /ws/sensors")

            while True:
                # Use wait_for to handle both incoming messages and periodic updates
                try:
                    # Try to receive a message with a 2-second timeout
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=2.0
                    )
                    
                    logger.debug(f"📥 Message from {client_id}: {data[:50]}..." if len(data) > 50 else f"📥 Message from {client_id}: {data}")

                    # Handle client messages (subscriptions, filters, etc.)
                    await ws_manager_instance.handle_client_message(client_id, data)

                except asyncio.TimeoutError:
                    # No message received, check if it's time to send sensor update
                    logger.debug(f"⏱️  No message from {client_id}, checking for update...")
                    current_time = datetime.utcnow()
                    time_since_update = (current_time - last_update_time).total_seconds()

                    if time_since_update >= 2.0:  # Send update every 2 seconds
                        try:
                            # Get latest sensor data
                            pipeline = [
                                {"$sort": {"timestamp": -1}},
                                {"$group": {
                                    "_id": "$equipment_id",
                                    "latest": {"$first": "$$ROOT"}
                                }},
                                {"$replaceRoot": {"newRoot": "$latest"}},
                                {"$limit": 10}
                            ]

                            sensors = list(sensor_collection.aggregate(pipeline))
                            logger.debug(f"⚙️ Retrieved {len(sensors)} sensors from sensor_events")
                            
                            sensors = convert_objectids(sensors)
                            logger.debug(f"⚙️ Processing data for client {client_id}")

                            if sensors:
                                # Send update to client
                                success = await ws_manager_instance.send_json_to_client(
                                    client_id,
                                    {
                                        "type": "sensor_update",
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "data": sensors
                                    }
                                )
                                
                                if success:
                                    logger.debug(f"📊 Sent sensor update to {client_id}: {len(sensors)} sensors")
                                else:
                                    # If send failed, connection is likely dead
                                    logger.warning(f"⚠️  Failed to send update to {client_id}")
                                    break

                            last_update_time = current_time

                        except Exception as e:
                            logger.error(f"❌ Error sending sensor update to {client_id}: {e}")

    except WebSocketDisconnect:
        await ws_manager_instance.disconnect(client_id)
        logger.info(f"🔌 WebSocket /ws/sensors - Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"❌ WebSocket /ws/sensors - Error for {client_id}: {e}", exc_info=True)
        await ws_manager_instance.disconnect(client_id)


@router.websocket("/ws/wafers")
async def websocket_wafers(websocket: WebSocket):
    """
    WebSocket endpoint for real-time wafer inspection updates with periodic polling
    """
    # Validate dependencies
    if ws_manager_instance is None:
        logger.error("❌ WebSocket /ws/wafers - ws_manager not initialized")
        await websocket.close(code=1011, reason="Server not initialized")
        return
    
    # Connect with WebSocket manager (using injected instance for consistency)
    client_id = await ws_manager_instance.connect(
        websocket,
        connection_type=ConnectionType.WAFERS
    )
    
    logger.info(f"🔌 WebSocket /ws/wafers - Client {client_id} connected")
    logger.debug(f"⚙️ Using connection type: {ConnectionType.WAFERS}")

    try:
        with get_mongodb_connector() as mdb_connector:
            wafer_collection = mdb_connector.get_collection("wafer_defects")
            last_update_time = datetime.utcnow()
            logger.debug(f"⚙️ MongoDB connector established for /ws/wafers")

            while True:
                # Use wait_for to handle both incoming messages and periodic updates
                try:
                    # Try to receive a message with a 5-second timeout
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=5.0
                    )
                    
                    logger.debug(f"📥 Message from {client_id}: {data[:50]}..." if len(data) > 50 else f"📥 Message from {client_id}: {data}")

                    # Handle client messages (subscriptions, filters, etc.)
                    await ws_manager_instance.handle_client_message(client_id, data)

                except asyncio.TimeoutError:
                    # No message received, check if it's time to send wafer update
                    logger.debug(f"⏱️  No message from {client_id}, checking for update...")
                    current_time = datetime.utcnow()
                    time_since_update = (current_time - last_update_time).total_seconds()

                    if time_since_update >= 5.0:  # Send update every 5 seconds
                        try:
                            # Get latest wafer inspection
                            latest_wafer = wafer_collection.find_one(
                                {},
                                sort=[("inspection_timestamp", -1)]
                            )

                            if latest_wafer:
                                wafer_id = latest_wafer.get("wafer_id", "unknown")
                                logger.debug(f"⚙️ Retrieved latest wafer: {wafer_id}")
                                
                                # Remove large image data
                                if "ink_map" in latest_wafer and "thumbnail_base64" in latest_wafer["ink_map"]:
                                    latest_wafer["ink_map"]["has_thumbnail"] = True
                                    del latest_wafer["ink_map"]["thumbnail_base64"]
                                    logger.debug(f"⚙️ Removed thumbnail_base64 from wafer {wafer_id}")

                                latest_wafer = convert_objectids(latest_wafer)
                                logger.debug(f"⚙️ Processing data for client {client_id}")

                                # Send to client using manager
                                success = await ws_manager_instance.send_to_client(client_id, {
                                    "type": "wafer_update",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "wafer": latest_wafer
                                })

                                if success:
                                    logger.debug(f"📊 Sent wafer update to {client_id}: wafer_id={wafer_id}")
                                else:
                                    # If send failed, connection is likely dead
                                    logger.warning(f"⚠️  Failed to send update to {client_id}")
                                    break

                            last_update_time = current_time

                        except Exception as e:
                            logger.error(f"❌ Error sending wafer update to {client_id}: {e}")

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket /ws/wafers - Client {client_id} disconnected")
        await ws_manager_instance.disconnect(client_id)
    except Exception as e:
        logger.error(f"❌ WebSocket /ws/wafers - Error for {client_id}: {e}", exc_info=True)
        await ws_manager_instance.disconnect(client_id)


@router.websocket("/ws/agent")
async def websocket_agent_progress(websocket: WebSocket):
    """
    WebSocket endpoint for real-time AI agent progress updates
    Receives agent_progress messages broadcasted during multi-agent pipeline execution
    """
    # Validate dependencies
    if ws_manager_instance is None:
        logger.error("❌ WebSocket /ws/agent - ws_manager not initialized")
        await websocket.close(code=1011, reason="Server not initialized")
        return

    # Connect with WebSocket manager
    client_id = await ws_manager_instance.connect(
        websocket=websocket,
        connection_type=ConnectionType.AGENT
    )


    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            logger.debug(f"📥 Message from {client_id}: {data[:50]}..." if len(data) > 50 else f"📥 Message from {client_id}: {data}")

            # Handle client messages (subscriptions, filters, etc.)
            await ws_manager_instance.handle_client_message(client_id, data)

    except WebSocketDisconnect:
        await ws_manager_instance.disconnect(client_id)
    except Exception as e:
        await ws_manager_instance.disconnect(client_id)

