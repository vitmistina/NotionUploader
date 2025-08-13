from fastapi import Query

timezone_query = Query(
    default="Europe/Prague",
    description="IANA timezone for local time, defaults to Prague.",
)
