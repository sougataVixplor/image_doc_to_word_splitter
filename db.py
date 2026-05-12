"""
db.py — MongoDB CRUD helpers for the Bengali Word Splitter app.
"""

import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "bengali_words")

_client: MongoClient | None = None


def get_db():
    """Return the MongoDB database, reusing a cached client."""
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    return _client[MONGODB_DB_NAME]


# ---------------------------------------------------------------------------
# Serial number management (auto-increment via a counters collection)
# ---------------------------------------------------------------------------

def get_next_serial() -> int:
    """Atomically increment and return the next serial number."""
    db = get_db()
    result = db.counters.find_one_and_update(
        {"_id": "text_serial"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return result["seq"]


def _peek_next_serial() -> int:
    """Return what the next serial number would be without incrementing."""
    db = get_db()
    doc = db.counters.find_one({"_id": "text_serial"})
    return (doc["seq"] + 1) if doc else 1


# ---------------------------------------------------------------------------
# Bengali word extraction
# ---------------------------------------------------------------------------

def extract_words(paragraph: str) -> list[str]:
    """
    Split a Bengali paragraph into tokens, preserving punctuation attached
    to words (e.g. 'র.' stays as 'র.') and discarding blank tokens.
    """
    # Split on whitespace; keep non-empty tokens
    tokens = [t.strip() for t in paragraph.split() if t.strip()]
    return tokens


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

VALID_CLASSES = [
    "MYTHOLOGY",
    "LAND",
    "LITERATURE",
    "SCIENCE",
    "GEOGRAPHY",
    "BANGRAGY",
]


def insert_text(class_name: str, paragraph: str) -> dict:
    """
    Insert a new text document.
    Returns the inserted document (with serial number).
    Raises ValueError for bad class, PyMongoError on DB failure.
    """
    if class_name not in VALID_CLASSES:
        raise ValueError(f"Invalid class '{class_name}'. Must be one of {VALID_CLASSES}")

    serial = get_next_serial()
    words = extract_words(paragraph)
    now = datetime.now(tz=timezone.utc)

    doc = {
        "serial": serial,
        "class": class_name,
        "paragraph": paragraph,
        "words": words,
        "word_count": len(words),
        "created_at": now,
        "updated_at": now,
    }
    db = get_db()
    db.texts.insert_one(doc)
    return doc


def get_all_texts(class_filter: str | None = None) -> list[dict]:
    """
    Return all text documents, sorted by serial number.
    Optionally filter by class.
    """
    db = get_db()
    query = {}
    if class_filter and class_filter != "ALL":
        query["class"] = class_filter
    cursor = db.texts.find(query, {"_id": 0}).sort("serial", ASCENDING)
    return list(cursor)


def get_text_by_serial(serial: int) -> dict | None:
    """Fetch a single text document by its serial number."""
    db = get_db()
    return db.texts.find_one({"serial": serial}, {"_id": 0})


def update_text(serial: int, paragraph: str, class_name: str) -> bool:
    """
    Update paragraph and/or class of an existing entry.
    Re-derives the word array automatically.
    Returns True if a document was modified, False otherwise.
    """
    if class_name not in VALID_CLASSES:
        raise ValueError(f"Invalid class '{class_name}'.")

    words = extract_words(paragraph)
    db = get_db()
    result = db.texts.update_one(
        {"serial": serial},
        {
            "$set": {
                "paragraph": paragraph,
                "class": class_name,
                "words": words,
                "word_count": len(words),
                "updated_at": datetime.now(tz=timezone.utc),
            }
        },
    )
    return result.modified_count > 0


def delete_text(serial: int) -> bool:
    """
    Delete a text document by serial number.
    Returns True if deleted, False if not found.
    """
    db = get_db()
    result = db.texts.delete_one({"serial": serial})
    return result.deleted_count > 0


def peek_next_serial() -> int:
    """Public alias for UI display (shows what serial will be assigned next)."""
    return _peek_next_serial()
