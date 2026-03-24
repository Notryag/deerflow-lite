from __future__ import annotations


def search_web(query: str, top_k: int = 5) -> list[dict[str, str]]:
    return [
        {
            "title": f"Stub result {index} for {query}",
            "url": f"https://example.com/search/{index}",
            "snippet": f"Mock web result {index} related to: {query}",
            "source": "web",
        }
        for index in range(1, top_k + 1)
    ]
