from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv()


client = TavilyClient(
    api_key=os.getenv("TRAVILIL_API_KEY"),
)


def travily_serach(query):
    response = client.search(query=query, max_results=5)
    result = []
    for i, r in enumerate(response["results"]):
        title = r.get("title", "unknown")
        url = r.get("url", "unknown")
        snippet = r.get("snippet", "unknown")
        if len(snippet) > 300:
            snippet = snippet[:300].rsplit(" ", 1)[0] + "..."
        result.append(f"{i}. **{title}**\n {url} \n{snippet}")
    return "\n\n".join(result)
