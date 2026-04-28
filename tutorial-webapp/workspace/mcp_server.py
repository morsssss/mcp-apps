import requests
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP

API_BASE_URL = "https://dog.ceo/api"
RESOURCE_URI = "ui://dog_image"

mcp = FastMCP("dogs")
view_resource = {"resourceUri": RESOURCE_URI}


@mcp.tool(app=view_resource)
def get_random_dog() -> str:
    """Retrieves the URL of an image of a random dog and displays it."""
    resp = requests.get(f"{API_BASE_URL}/breeds/image/random")
    return resp.json()["message"]


@mcp.tool(app=view_resource)
def get_dog_by_breed(breed: str) -> str:
    """Retrieves a dog image for the given breed name."""
    resp = requests.get(f"{API_BASE_URL}/breed/{breed}/images")
    return resp.json()["message"][0]


@mcp.resource(
    RESOURCE_URI,
    app=AppConfig(
        csp=ResourceCSP(
            resource_domains=["https://unpkg.com", "https://images.dog.ceo"],
            connect_domains=["http://dog.ceo"],
        )
    ),
)
def view() -> str:
    with open("view.html") as f:
        return f.read()


if __name__ == "__main__":
    mcp.run()
