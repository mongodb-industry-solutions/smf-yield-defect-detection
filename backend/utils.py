from bson import ObjectId
from typing import Any
from datetime import datetime

def convert_objectids(item: Any) -> Any:
    """
    Recursively convert ObjectIds to strings and datetime objects to ISO format strings.

    This is useful when converting a PyMongo document to a JSON-serializable format. 
    ObjectIds and datetime objects are not serializable to JSON, so they must be converted to strings

    Args:
        item (Any): A document or field to convert

    Returns:
        Any: The document or field with all ObjectIds and datetimes converted
    """
    if isinstance(item, list):
        return [convert_objectids(i) for i in item]
    elif isinstance(item, dict):
        return {k: convert_objectids(v) for k, v in item.items()}
    elif isinstance(item, ObjectId):
        return str(item)
    elif isinstance(item, datetime):
        return item.isoformat()
    else:
        return item

def format_document(item: Any, max_array_length: int = 10) -> Any:
    """
    Recursively convert ObjectIds to strings, datetime objects to ISO format strings,
    and if the item is a list that exceeds `max_array_length`, only return the first 
    max_array_length items with a summary string indicating how many items were omitted.

    Args:
        item (Any): A document or field to convert
        max_array_length (int): The maximum number of items to return in an array

    Returns:
        Any: The document or field with all ObjectIds and datetimes converted
    """
    if isinstance(item, list):
        if len(item) > max_array_length:
            truncated = [format_document(i, max_array_length) for i in item[:max_array_length]]
            return truncated 
        else:
            return [format_document(i, max_array_length) for i in item]
    elif isinstance(item, dict):
        return {k: format_document(v, max_array_length) for k, v in item.items()}
    elif isinstance(item, ObjectId):
        return str(item)
    elif isinstance(item, datetime):
        return item.isoformat()
    elif isinstance(item, bytes):
        # Convert binary data to a hex string
        return item.hex()
    else:
        return item