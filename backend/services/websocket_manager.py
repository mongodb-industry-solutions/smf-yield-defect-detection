"""
WebSocket Connection Manager
Handles WebSocket connections with thread-safety, connection tracking, and broadcasting
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Types of WebSocket connections"""
    ALERTS = "alerts"
    SENSORS = "sensors"
    WAFERS = "wafers"
    AGENT = "agent"
    GENERAL = "general"


class WebSocketConnection:
    """Represents a single WebSocket connection with metadata"""

    def __init__(
        self,
        websocket: WebSocket,
        client_id: str,
        connection_type: ConnectionType = ConnectionType.GENERAL,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.websocket = websocket
        self.client_id = client_id
        self.connection_type = connection_type
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        self.metadata = metadata or {}

        # Client preferences for filtering
        self.subscriptions = {
            "equipment_ids": set(),  # Subscribe to specific equipment
            "alert_severities": set(),  # Subscribe to specific severities
            "event_types": set()  # Subscribe to specific event types
        }

    def update_subscriptions(self, subscriptions: Dict[str, List[str]]):
        """Update client's subscription preferences"""
        for key, values in subscriptions.items():
            if key in self.subscriptions:
                self.subscriptions[key] = set(values)

    def should_receive(self, message: Dict[str, Any]) -> bool:
        """Check if this connection should receive a message based on filters"""
        # If no filters set, receive all messages
        if not any(self.subscriptions.values()):
            return True

        # Check equipment filter
        if self.subscriptions["equipment_ids"]:
            equipment_id = message.get("equipment_id")
            if equipment_id and equipment_id not in self.subscriptions["equipment_ids"]:
                return False

        # Check severity filter
        if self.subscriptions["alert_severities"]:
            severity = message.get("severity")
            if severity and severity not in self.subscriptions["alert_severities"]:
                return False

        # Check event type filter
        if self.subscriptions["event_types"]:
            event_type = message.get("type")
            if event_type and event_type not in self.subscriptions["event_types"]:
                return False

        return True


class WebSocketManager:
    """
    Manages WebSocket connections with thread-safety and advanced features
    """

    def __init__(self):
        self._connections: Dict[str, WebSocketConnection] = {}
        self._lock = asyncio.Lock()
        self._connection_count = 0
        self._message_count = 0
        self._error_count = 0

        # Track connections by type for efficient filtering
        self._connections_by_type: Dict[ConnectionType, Set[str]] = {
            conn_type: set() for conn_type in ConnectionType
        }

        logger.info("WebSocketManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        client_id: Optional[str] = None,
        connection_type: ConnectionType = ConnectionType.GENERAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new WebSocket connection

        Args:
            websocket: The WebSocket connection
            client_id: Optional client ID (will be generated if not provided)
            connection_type: Type of connection
            metadata: Optional metadata for the connection

        Returns:
            The client ID
        """
        await websocket.accept()

        # Generate client ID if not provided
        if not client_id:
            client_id = str(uuid.uuid4())

        async with self._lock:
            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                client_id=client_id,
                connection_type=connection_type,
                metadata=metadata
            )

            # Store connection
            self._connections[client_id] = connection
            self._connections_by_type[connection_type].add(client_id)
            self._connection_count += 1

            logger.info(
                f"WebSocket connected: {client_id} "
                f"(type: {connection_type.value}, total: {len(self._connections)})"
            )

        # Don't send welcome message immediately - let the client stabilize
        # The welcome message was causing disconnections
        logger.debug(f"WebSocket {client_id} ready for messages")

        return client_id

    async def disconnect(self, client_id: str):
        """
        Remove a WebSocket connection

        Args:
            client_id: The client ID to disconnect
        """
        async with self._lock:
            if client_id in self._connections:
                connection = self._connections[client_id]

                # Remove from type tracking
                self._connections_by_type[connection.connection_type].discard(client_id)

                # Remove connection
                del self._connections[client_id]

                logger.info(
                    f"WebSocket disconnected: {client_id} "
                    f"(type: {connection.connection_type.value}, remaining: {len(self._connections)})"
                )
            else:
                logger.warning(f"Attempted to disconnect unknown client: {client_id}")

    async def send_to_client(
        self,
        client_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Send a message to a specific client

        Args:
            client_id: The client to send to
            message: The message dictionary to send

        Returns:
            True if sent successfully, False otherwise
        """
        async with self._lock:
            if client_id not in self._connections:
                logger.warning(f"Client {client_id} not found")
                return False

            connection = self._connections[client_id]

        try:
            # Check if WebSocket is still open before sending
            if connection.websocket.client_state.name != "CONNECTED":
                logger.warning(f"WebSocket {client_id} is not in CONNECTED state: {connection.websocket.client_state.name}")
                await self.disconnect(client_id)
                return False

            # Convert message to JSON
            if isinstance(message, dict):
                message_str = json.dumps(message)
            else:
                message_str = str(message)

            # Send message
            await connection.websocket.send_text(message_str)
            self._message_count += 1

            logger.debug(f"Sent message to {client_id}: {message.get('type', 'unknown')}")
            return True

        except WebSocketDisconnect as e:
            logger.info(f"WebSocket {client_id} disconnected while sending")
            self._error_count += 1

            # Remove dead connection
            await self.disconnect(client_id)
            return False

        except Exception as e:
            logger.error(f"Error sending to {client_id}: {type(e).__name__}: {str(e)}")
            self._error_count += 1

            # Remove dead connection
            await self.disconnect(client_id)
            return False

    async def send_json_to_client(
        self,
        client_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Send a JSON message to a specific client

        Args:
            client_id: The client to send to
            message: The message dictionary to send

        Returns:
            True if sent successfully, False otherwise
        """
        async with self._lock:
            if client_id not in self._connections:
                logger.warning(f"Client {client_id} not found")
                return False

            connection = self._connections[client_id]

        try:
            # Check if WebSocket is still open before sending
            if connection.websocket.client_state.name != "CONNECTED":
                logger.warning(f"WebSocket {client_id} is not in CONNECTED state: {connection.websocket.client_state.name}")
                await self.disconnect(client_id)
                return False

            # Send JSON message
            await connection.websocket.send_json(message)
            self._message_count += 1

            logger.debug(f"Sent JSON to {client_id}: {message.get('type', 'unknown')}")
            return True

        except WebSocketDisconnect as e:
            logger.info(f"WebSocket {client_id} disconnected while sending")
            self._error_count += 1

            # Remove dead connection
            await self.disconnect(client_id)
            return False

        except Exception as e:
            logger.error(f"Error sending JSON to {client_id}: {type(e).__name__}: {str(e)}")
            self._error_count += 1

            # Remove dead connection
            await self.disconnect(client_id)
            return False

    async def broadcast(
        self,
        message: Dict[str, Any],
        connection_type: Optional[ConnectionType] = None,
        filter_fn: Optional[Callable[[WebSocketConnection], bool]] = None
    ) -> int:
        """
        Broadcast a message to all or filtered connections

        Args:
            message: The message to broadcast
            connection_type: Optional - only send to specific connection type
            filter_fn: Optional - custom filter function

        Returns:
            Number of clients the message was sent to
        """
        # Get list of connections to send to
        async with self._lock:
            if connection_type:
                # Get connections of specific type
                client_ids = list(self._connections_by_type[connection_type])
            else:
                # Get all connections
                client_ids = list(self._connections.keys())

        sent_count = 0
        failed_clients = []

        for client_id in client_ids:
            async with self._lock:
                if client_id not in self._connections:
                    continue

                connection = self._connections[client_id]

                # Apply custom filter if provided
                if filter_fn and not filter_fn(connection):
                    continue

                # Check subscription filters
                if not connection.should_receive(message):
                    continue

            # Send message (outside lock to prevent blocking)
            success = await self.send_to_client(client_id, message)

            if success:
                sent_count += 1
            else:
                failed_clients.append(client_id)

        if failed_clients:
            logger.warning(f"Failed to send to {len(failed_clients)} clients")

        logger.info(
            f"Broadcast message type '{message.get('type', 'unknown')}' "
            f"to {sent_count}/{len(client_ids)} clients"
        )

        return sent_count

    async def broadcast_to_equipment_subscribers(
        self,
        equipment_id: str,
        message: Dict[str, Any]
    ) -> int:
        """
        Broadcast to clients subscribed to specific equipment

        Args:
            equipment_id: The equipment ID
            message: The message to send

        Returns:
            Number of clients the message was sent to
        """
        def equipment_filter(conn: WebSocketConnection) -> bool:
            return (
                not conn.subscriptions["equipment_ids"] or
                equipment_id in conn.subscriptions["equipment_ids"]
            )

        # Add equipment_id to message for filtering
        message["equipment_id"] = equipment_id

        return await self.broadcast(message, filter_fn=equipment_filter)

    async def update_client_subscriptions(
        self,
        client_id: str,
        subscriptions: Dict[str, List[str]]
    ):
        """
        Update a client's subscription preferences

        Args:
            client_id: The client ID
            subscriptions: Dictionary of subscription preferences
        """
        async with self._lock:
            if client_id in self._connections:
                self._connections[client_id].update_subscriptions(subscriptions)
                logger.info(f"Updated subscriptions for {client_id}: {subscriptions}")

    async def handle_client_message(
        self,
        client_id: str,
        message: str
    ):
        """
        Handle incoming message from a client

        Args:
            client_id: The client ID
            message: The message received
        """
        try:
            # Parse message
            data = json.loads(message) if message else {}

            # Handle different message types
            message_type = data.get("type")

            if message_type == "subscribe":
                # Update client subscriptions
                await self.update_client_subscriptions(
                    client_id,
                    data.get("subscriptions", {})
                )

                # Send confirmation
                await self.send_to_client(client_id, {
                    "type": "subscription_updated",
                    "subscriptions": data.get("subscriptions", {}),
                    "timestamp": datetime.utcnow().isoformat()
                })

            elif message_type == "ping":
                # Respond to ping
                await self.send_to_client(client_id, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Update last ping time
                async with self._lock:
                    if client_id in self._connections:
                        self._connections[client_id].last_ping = datetime.utcnow()

            else:
                logger.debug(f"Received message from {client_id}: {message_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {client_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current connections

        Returns:
            Dictionary with connection statistics
        """
        stats = {
            "total_connections": len(self._connections),
            "connections_by_type": {},
            "total_messages_sent": self._message_count,
            "total_errors": self._error_count,
            "total_connections_handled": self._connection_count
        }

        # Count by type
        for conn_type in ConnectionType:
            stats["connections_by_type"][conn_type.value] = len(
                self._connections_by_type[conn_type]
            )

        return stats

    async def close_all(self):
        """Close all connections gracefully"""
        logger.info(f"Closing all {len(self._connections)} connections...")

        # Send closing message to all clients
        await self.broadcast({
            "type": "server_closing",
            "message": "Server is shutting down",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Close all connections
        async with self._lock:
            for client_id, connection in list(self._connections.items()):
                try:
                    await connection.websocket.close()
                except Exception as e:
                    logger.error(f"Error closing connection {client_id}: {e}")

            self._connections.clear()
            for conn_type in ConnectionType:
                self._connections_by_type[conn_type].clear()

        logger.info("All connections closed")


# Global instance (singleton pattern)
_manager_instance: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """
    Get the global WebSocketManager instance (singleton)

    Returns:
        The WebSocketManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WebSocketManager()
    return _manager_instance