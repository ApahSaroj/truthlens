import json


def load_trusted_sources():

    with open(
        "data/trusted_sources.json",
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def get_domain_category(domain):

    sources = load_trusted_sources()

    for category, domains in sources.items():

        if domain in domains:
            return category

    return "unknown"
