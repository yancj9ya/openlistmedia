import sys
from pprint import pprint

from config_loader import get_value, load_config
from tmdb_sdk import TMDbAPIError, TMDbClient, TMDbHTTPError


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    config = load_config()
    read_access_token = str(get_value(config, "tmdb", "read_access_token", default="") or "").strip()
    api_key = str(get_value(config, "tmdb", "api_key", default="") or "").strip()
    language = str(get_value(config, "tmdb", "language", default="zh-CN") or "zh-CN").strip()
    query = str(get_value(config, "tests", "tmdb", "query", default="Inception") or "Inception").strip()

    try:
        with TMDbClient(read_access_token or None, api_key=api_key or None) as client:
            print("== Configuration ==")
            config = client.configuration_details()
            pprint(config)

            print(f"\n== Search Movie: {query} ==")
            movie_search = client.search_movie(query, language=language, page=1)
            pprint(movie_search)

            results = movie_search.get("results", [])
            if results:
                movie_id = results[0]["id"]
                print(f"\n== Movie Details: {movie_id} ==")
                details = client.movie_details(movie_id, language=language, append_to_response="images,videos")
                pprint(details)

                poster_path = details.get("poster_path")
                if poster_path:
                    print("\n== Poster URL ==")
                    print(client.build_image_url(poster_path, size="w500"))

            print("\n== Trending All / Day ==")
            pprint(client.trending("all", "day", language=language))

        return 0
    except (TMDbAPIError, TMDbHTTPError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
