// Netlify Function: öffentlicher MCP-Endpunkt unter /mcp (Streamable HTTP, ohne Anmeldung).
// Die Daten unter data/ werden über included_files in netlify.toml mit ausgeliefert.

import { handleHttp } from "../../src/http.mjs";

export default (req) => handleHttp(req);

export const config = {
  path: "/mcp",
  rateLimit: {
    windowSize: 60,
    windowLimit: 120,
    aggregateBy: ["ip", "domain"],
  },
};
