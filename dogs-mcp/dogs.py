import requests
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP

API_BASE_URL = "https://dog.ceo/api"
HTML_FILENAME = "view_dropdown.html" # this can also be `view.html`
RESOURCE_URI = "ui://dog_image"

viewResource = {"resourceUri": RESOURCE_URI}

mcp = FastMCP("dogs")

@mcp.tool(app = viewResource)
def get_random_dog() -> str:
    """Retrieves the URL of an image of a random dog."""
    response = requests.get(API_BASE_URL + "/breeds/image/random")
    json = response.json()
    return json["message"]

# The API returns a list of all the images of this breed. Just return the first one.
@mcp.tool(app = viewResource)
def get_dog_by_breed(breed: str) -> str:
    """Retrieves the URL of an image of a dog of a desired breed"""
    response = requests.get(f"{API_BASE_URL}/breed/{breed}/images")
    json = response.json()
    return json["message"][0]

# This resource contains the HTML for our webview.
# We also need to give our iframe permission to connect to external domains.
@mcp.resource(
    RESOURCE_URI,
    app=AppConfig(
        csp=ResourceCSP(
            resource_domains=["https://unpkg.com", "https://images.dog.ceo"],
            connect_domains=["https://dog.ceo"]
        )
    )
)
def view() -> str:
    with open(HTML_FILENAME) as f:
        html = f.read()
    return html

if __name__ == "__main__":
    mcp.run()
