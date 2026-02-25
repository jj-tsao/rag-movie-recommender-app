import asyncio
from datetime import date
from typing import List, Optional
import logging

import httpx
from tqdm import tqdm

logging.getLogger("httpx").setLevel(logging.WARNING)


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str, max_connections: int = 15, timeout: float = 10.0):
        self.api_key = api_key
        limits = httpx.Limits(
            max_connections=max_connections, max_keepalive_connections=max_connections
        )
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=limits,
            headers={"Accept": "application/json"},
        )
        self.semaphore = asyncio.Semaphore(max_connections)

    def build_discover_url(
        self, media_type: str, page: int, rating: float, vote_count: int
    ) -> str:
        today = date.today()
        date_param = (
            "primary_release_date.lte"
            if media_type == "movie"
            else "first_air_date.lte"
        )
        url = (
            f"{self.BASE_URL}/discover/{media_type}"
            f"?api_key={self.api_key}&language=en-US&page={page}&region=US"
            f"&{date_param}={today}&vote_average.gte={rating}&vote_count.gte={vote_count}&sort_by=popularity.desc"
        )
        if media_type == "movie":
            url += "&without_genres=10770"
        else:
            url += (
                "&include_null_first_air_dates=false"
                "&watch_region=US"
                "&with_watch_monetization_types=flatrate|free|ads|rent|buy"
                "&without_genres=10767,10763"
            )
        return url

    async def get(self, url: str):
        async with self.semaphore:
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"[HTTP Error] {e.response.status_code}: {url}")
            except httpx.RequestError as e:
                print(f"[Request Error] {e}")
            except Exception as e:
                print(f"[Unexpected Error] {e}")
        return None

    async def get_with_retry(self, url: str, retries: int = 2, delay: float = 1.0):
        for attempt in range(retries + 1):
            result = await self.get(url)
            if result:
                return result
            if attempt < retries:
                await asyncio.sleep(delay * (2**attempt))  # Exponential backoff
        return None

    async def fetch_media_ids(
        self,
        media_type: str,  # "movie" or "tv"
        page: int = 1,
        rating: float = 0,
        vote_count: int = 0,
    ) -> List[int]:
        url = self.build_discover_url(media_type, page, rating, vote_count)
        data = await self.get_with_retry(url)
        return [movie["id"] for movie in data.get("results", [])] if data else []

    async def fetch_media_ids_bulk(
        self,
        media_type: str,  # "movie" or "tv"
        media_count_in_k: int = 1,
        rating: float = 0,
        vote_count: int = 0,
    ) -> List[int]:
        total_pages = int(media_count_in_k * 50)
        print(
            f"📦 Fetching {media_type.upper()} IDs from {total_pages} pages with rating > {rating}..."
        )
        tasks = [
            self.fetch_media_ids(media_type, page, rating, vote_count)
            for page in range(1, total_pages + 1)
        ]
        results = await asyncio.gather(*tasks)
        all_ids = list(dict.fromkeys(
            mid for sublist in results if isinstance(sublist, list) for mid in sublist
        ))
        print(f"✅ Fetched {len(all_ids):,} unique {media_type.upper()} IDs")
        return all_ids

    async def fetch_media_details(
        self, media_type: str, media_id: int
    ) -> Optional[dict]:
        base = f"{self.BASE_URL}/{media_type}/{media_id}"
        details_url = f"{base}?api_key={self.api_key}"
        credits_url = (
            f"{base}/credits?api_key={self.api_key}"
            if media_type == "movie"
            else f"{base}/aggregate_credits?api_key={self.api_key}"
        )
        keywords_url = f"{base}/keywords?api_key={self.api_key}"
        providers_url = f"{base}/watch/providers?api_key={self.api_key}"
        video_url = f"{base}/videos?api_key={self.api_key}"
        external_ids_url = f"{base}/external_ids?api_key={self.api_key}"

        media_details = await self.get_with_retry(details_url) or {}

        credits_data, keywords_data, providers_data, video_data, external_id_data = (
            await asyncio.gather(
                self.get_with_retry(credits_url),
                self.get_with_retry(keywords_url),
                self.get_with_retry(providers_url),
                self.get_with_retry(video_url),
                self.get_with_retry(external_ids_url),
            )
        )

        if media_type == "movie":
            if credits_data:
                crew = credits_data.get("crew", [])

                media_details["director"] = next(
                    (c["name"] for c in crew if c["job"] == "Director"), "Unknown"
                )
                cast = credits_data.get("cast", [])

                media_details["stars"] = [
                    c.get("name") for c in cast[:3] if "name" in c
                ]
            else:
                media_details["director"] = "Unknown"

                media_details["stars"] = []
        else:
            media_details["creator"] = [
                c.get("name")
                for c in media_details.get("created_by", [])
                if "name" in c
            ]
            if credits_data:
                cast = credits_data.get("cast", [])

                media_details["stars"] = [
                    c.get("name") for c in cast[:3] if "name" in c
                ]
            else:
                media_details["stars"] = []

        if keywords_data:
            keyword_key = "keywords" if media_type == "movie" else "results"

            media_details["keywords"] = [
                kw["name"] for kw in keywords_data.get(keyword_key, [])
            ]

        if video_data:
            videos = video_data.get("results", [])

            def has_keywords(name: str, keywords: list[str]) -> bool:
                name = name.lower()
                return all(kw in name for kw in keywords)

            def semantic_score(video: dict) -> float:
                name = video["name"].lower()
                score = 0
                if has_keywords(name, ["official", "us", "trailer"]):
                    score += 1000
                elif "official trailer" in name:
                    score += 800
                elif "official" in name:
                    score += 500
                if video["official"]:
                    score += 500
                score += video.get("size", 0) / 10
                return score

            def sort_trailer(videos):
                trailers = [
                    v
                    for v in videos
                    if v["type"] == "Trailer" and v["site"] == "YouTube"
                ]
                if not trailers:
                    return None
                return max(trailers, key=semantic_score)

            trailer = sort_trailer(videos)

            media_details["trailer_key"] = trailer["key"] if trailer else None

        if providers_data:
            us_data = providers_data.get("results", {}).get("US", {})
            providers = us_data.get("flatrate", []) + us_data.get("ads", [])
            if providers:
                media_details["providers"] = [p["provider_id"] for p in providers]

        if external_id_data:
            media_details["imdb_id"] = external_id_data.get("imdb_id", "")

        return media_details

    async def fetch_all_media_details(
        self, media_type: str, media_ids: List[int]
    ) -> List[dict]:
        tasks = [self.fetch_media_details(media_type, mid) for mid in media_ids]

        media_details = []
        for future in tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=f"🎥 Fetching {media_type.upper()} details (might take a while...)",
        ):
            try:
                media = await future
                if media:
                    media_details.append(media)
            except Exception as e:
                print(f"❌ Error fetching {media_type.upper()} details: {e}")

        return media_details

    async def aclose(self):
        await self.client.aclose()
