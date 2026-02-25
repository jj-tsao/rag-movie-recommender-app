import os
from dotenv import load_dotenv
from reelix_core.config import (
    QDRANT_MOVIE_COLLECTION_NAME,
)
from reelix_retrieval.qdrant_filter import build_qfilter
from reelix_retrieval.vectorstore import connect_qdrant

load_dotenv()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_ENDPOINT = os.getenv("QDRANT_ENDPOINT")

if not QDRANT_API_KEY:
    raise ValueError("Missing API key(s).")
if (
    not QDRANT_ENDPOINT
):
    raise ValueError("Missing QDrant URL or collection name.")


TEASER_TITLES = {
    "smart_thoughtful": [
        {
            "title": "Parasite",
            "release_year": 2019,
        },
        {
            "title": "Everything Everywhere All at Once",
            "release_year": 2022,
        },
        {
            "title": "Interstellar",
            "release_year": 2014,
        },
        {
            "title": "Ex Machina",
            "release_year": 2015,
        },
        {
            "title": "The Prestige",
            "release_year": 2006,
        },
        {
            "title": "Arrival",
            "release_year": 2016,
        },
        {
            "title": "Blade Runner 2049",
            "release_year": 2017,
        },
    ],
    "comfort_feel-good": [
        {
            "title": "Paddington 2",
            "release_year": 2017,
        },
        {
            "title": "Chef",
            "release_year": 2014,
        },
        {
            "title": "Lady Bird",
            "release_year": 2017,
        },
        {
            "title": "Amélie",
            "release_year": 2001,
        },
        {
            "title": "Her",
            "release_year": 2013,
        },

        {
            "title": "La La Land",
            "release_year": 2016,
        },
        {
            "title": "About Time",
            "release_year": 2013,
        },
    ],
    "kinetic_spectacle": [
        {
            "title": "Mad Max: Fury Road",
            "release_year": 2015,
        },
        {
            "title": "Top Gun: Maverick",
            "release_year": 2022,
        },
        {
            "title": "The Lord of the Rings: The Return of the King",
            "release_year": 2003,
        },
        {
            "title": "Spider-Man: Into the Spider-Verse",
            "release_year": 2018,
        },
        {
            "title": "Dune: Part Two",
            "release_year": 2024,
        },
        {
            "title": "Casino Royale",
            "release_year": 2006,
        }, 
        {
            "title": "Spirited Away",
            "release_year": 2001,            
        }
    ],
}


def query_qdrant(filter):
    points, _ = qdrant_client.scroll(
        collection_name=QDRANT_MOVIE_COLLECTION_NAME,
        scroll_filter=filter,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    return points


qdrant_client = connect_qdrant(QDRANT_API_KEY, QDRANT_ENDPOINT)

for genre, medias in TEASER_TITLES.items():
    print(f"\n== {genre} ==")
    for m in medias:
        filter = build_qfilter(titles=[m["title"]], release_year=m["release_year"])
        # print (m['title'])
        points = query_qdrant(filter)
        if points and points[0].payload:
            payload = points[0].payload
            m["media_id"] = payload["media_id"]
            m["genres"] = payload["genres"]
            m["poster_url"] = payload["poster_url"]
            m["backdrop_url"] = payload["backdrop_url"]
            m["trailer_key"] = payload["trailer_key"]
        else:
            print(f"Missing {m['title']}")
            m["poster_url"] = ""
            m["media_id"] = ""

TEASER_TITLES
