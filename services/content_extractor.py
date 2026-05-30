import requests
from bs4 import BeautifulSoup


def extract_from_url(url: str):

    try:

        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "TruthLens/0.1"
            }
        )

        soup = BeautifulSoup(response.text, "html.parser")

        title = ""

        if soup.title:
            title = soup.title.get_text(strip=True)

        paragraphs = soup.find_all("p")

        content = " ".join(
            p.get_text(" ", strip=True)
            for p in paragraphs
        )

        return {
            "success": True,
            "title": title,
            "content": content[:10000]
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }
