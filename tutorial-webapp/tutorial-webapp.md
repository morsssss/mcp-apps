We want to create a web app that mimics a tutorial page in a documentation website.
Ideally the design would resemble https://platform.claude.com/docs .
The web app looks at a Markdown file named tutorial.md, and it renders that on a page.
Code blocks look like the ones on https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool , with little tabs for each programming language. Our options here are just Python and JavaScript, though.
Here's the neat thing. This tutorial is about making an MCP app. This tutorial page also includes:
* a simple MCP client
  * which has basic chatbot functionality, sending user prompts to Claude and displaying responses
  * which can call MCP tools, including MCP apps
* a user-editable HTML area for the MCP app view
* a user-editable Python area for the MCP app server

The MCP client, HTML area, and Python area can be discovered by an appropriate user action.

Finally, we'll need to deploy this somewhere public. Vercel, Netlify, Github pages are all possibilities.