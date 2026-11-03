from truthlens.readers import read_url


def extract_from_url(url: str):
    """Legacy wrapper around truthlens.readers.read_url (paragraphs, list items, table rows)."""
    try:
        blocks, meta = read_url(url)
        return {"success": True, "title": meta.get("title", ""), "content": "\n\n".join(b.text for b in blocks)}
    except Exception as e:
        return {"success": False, "error": str(e)}
