/* Not currently in use */

import { App } from
"https://unpkg.com/@modelcontextprotocol/ext-apps@0.4.0/app-with-deps";

const app = new App({ name: "Dog viewer" });

// We expect the tool to send us an img URL. The `content` array should just contain an element whose type is 'text', which contains this URL.
app.ontoolresult = ({ content }) => {
  console.error(content);
  const imgUrl = content[0].text;
  console.error(content[0].text)
  const img = document.querySelector('img');
  img.src = imgUrl;
};

await app.connect();