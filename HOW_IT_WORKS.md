# How TripMate works

This is a travel planner. You type a trip request in the browser. A set of agents gathers flights, hotels, weather, and a budget check, writes a draft, waits for you to approve or revise it, then writes the final plan.

## What we use, and why

| Piece | What it is | Why it is here |
| --- | --- | --- |
| Python 3.11 in the `travle` conda env | The language and the environment the app runs in | Every local script, including the weather server, uses this interpreter |
| FastAPI (`app.py`) | The web server | Receives the browser request and returns JSON |
| Uvicorn | The program that starts FastAPI | `python app.py` runs the site on `http://127.0.0.1:8000` |
| LangGraph (`backend.py`) | The agent workflow | Decides which agents run, in what order, and where the run pauses |
| Groq, model `openai/gpt-oss-20b` | The language model | Writes the guardrail decision, the agent plan, flight notes, the budget, the draft, and the final answer |
| PostgreSQL | The database | LangGraph saves each trip thread here so approval can resume the same run |
| Tavily MCP | A web search server | Hotel search |
| AviationStack MCP | A flight-data server started with `uvx` | Airport and airline lookups. Some calls fail on the free plan |
| OpenWeatherMap | The weather API | Current conditions and a short forecast |
| Custom weather MCP (`custom_weather_mcp.py`) | Our own small MCP server | Wraps OpenWeather so the agents call it the same way they call Tavily |
| `nest_asyncio` | A small async helper | Lets agents call async MCP tools from the normal LangGraph flow |
| Browser page (`templates/index.html`, `static/script.js`, `static/style.css`) | The screen you use | Sends the request, shows the draft, and sends approve or revise |

Secrets live only in `.env`: `GROQ_API_KEY`, `DATABASE_URL`, `TAVILY_API_KEY`, `AVIATIONSTACK_API_KEY`, `OPENWEATHERMAP_API_KEY`.

## The path of one trip

1. The page sends `POST /api/travel` with your message.
2. `run_travel_agent` starts a LangGraph run and gives it a `thread_id`.
3. The supervisor checks that the message is about travel, then picks which agents are needed.
4. The chosen agents run in this order: flights, hotels, weather, budget, itinerary.
5. The itinerary agent writes a draft. The graph then pauses and asks you to review it.
6. The page shows the draft with **Approve plan** and **Revise draft**.
7. Your choice goes to `POST /api/travel/resume`.
8. The final agent writes the polished plan. The page replaces the draft with that plan.

If the guardrail rejects the message, the run stops and the page shows the reason. No agents search for flights or hotels.

## Files

### `app.py` — the HTTP API

This file does not plan the trip. It only accepts the browser call, calls the backend, and sends JSON back.

- `TravelRequest` is the body of `POST /api/travel`: `message` and an optional `thread_id`.
- `ResumeRequest` is the body of `POST /api/travel/resume`: `thread_id`, `approved` (true or false), and optional `feedback`.
- `home` returns the HTML page.
- `travel_planner` starts a new plan.
- `resume_planner` continues a paused plan after you approve or ask for changes.
- `health_check` is a simple “the server is up” check.

The JSON always includes `success`. On a real plan it also includes `answer`, `requires_approval`, `weather_results`, `budget_results`, `itinerary`, `selected_agents`, `guardrail_allowed`, and `thread_id`.

### `backend.py` — the agents

`TravelState` is the shared notebook every agent reads and writes. Important fields:

- `user_query` is the original request.
- `selected_agents` is the list the supervisor chose.
- `trip_constraints` holds origin, destination, duration, and budget when the model could extract them.
- `flight_results`, `hotel_results`, `weather_results`, `budget_results` are the specialist notes.
- `itinerary` is the draft.
- `final_response` is the polished answer after approval.
- `guardrail_allowed` is false when the request is not about travel.

Functions:

- `get_database_url` reads `DATABASE_URL` and adds `sslmode=require` when it is missing.
- `_llm_text` sends one system instruction and one user prompt to Groq and returns the text.
- `_json_from_llm` pulls the first `{...}` object out of a model reply. The supervisor and the guardrail must answer in JSON.
- `_clip` shortens long tool text before it is sent to Groq. The free Groq limit is 8,000 tokens per minute, so full hotel pages cannot be pasted in.
- `_empty_constraints` is a blank origin, destination, duration, budget, and style.
- `supervisor_agent` does two model calls. First it decides whether the request is travel. Then it picks agents and extracts trip details. If parsing fails, it runs every agent so a bad JSON reply does not kill the trip.
- `guardrail_blocked_agent` writes the rejection message and ends the graph.
- `flight_agent` asks AviationStack for airports and airlines, then asks Groq for short booking guidance.
- `hotel_agent` searches the web with Tavily for places to stay.
- `weather_agent` asks Groq for the destination city, then calls the weather MCP for current conditions and a forecast.
- `budget_agent` reads the notes collected so far and says whether the budget looks realistic.
- `itinerary_agent` writes the draft and an approval message.
- `human_approval_agent` calls LangGraph `interrupt`. That pauses the run until `resume_travel_agent` sends `approved` and `feedback`.
- `final_agent` writes the seven-section answer. If you approved, it polishes the draft. If you revised, it applies your notes.
- `route_from_supervisor` sends a blocked request to the guardrail node, otherwise to the first selected agent.
- `route_after_agent` jumps to the next selected agent, then to the itinerary.
- `_serialize_result` turns the graph result into the dictionary FastAPI returns. If the graph is paused, `requires_approval` is true and `answer` is the draft.
- `run_travel_agent` starts a thread.
- `resume_travel_agent` continues that same thread after your review.

The model is `openai/gpt-oss-20b` with `max_tokens=800`. Replies are capped so one call stays inside the Groq token limit.

### `mcp_client.py` — connections to outside tools

MCP is the protocol the agents use to call tools that live in other processes.

- Tavily is remote. The client calls `https://mcp.tavily.com` with your API key. Used for hotel search (`tavily_mcp_search`).
- AviationStack is local. `uvx` starts the `aviationstack-mcp` package. Used by `aviation_mcp_call` for tools such as `list_airports` and `list_airlines`.
- Weather is local. The `travle` conda Python runs `custom_weather_mcp.py`. Used by `weather_mcp_search` and `forecast_mcp_search`.
- `extract_destination` is not an MCP tool. It asks Groq to return only the city or country name so the weather call has a place to look up.
- `initialize_mcp` loads Tavily and AviationStack tools once and keeps them.
- `initialize_weather_tools` loads only the weather server, so a weather call does not restart the other servers.
- `get_all_tools` prints every tool from every server. It is for checking the connection, not for the website.

### `custom_weather_mcp.py` — our weather server

Started by the conda Python, not by `uvx`.

- `get_current_weather(city)` calls OpenWeather current weather and returns city, temperature, feels-like, humidity, condition, and wind speed.
- `get_forecast(city)` calls the OpenWeather forecast and returns the first five time slots.
- `mcp.run(transport="stdio")` keeps the process alive so `mcp_client.py` can talk to it on standard input and output.

### The page

- `templates/index.html` is the layout: the request box, the result, and the approve or revise form.
- `static/script.js` sends `/api/travel`, and later `/api/travel/resume`. If `requires_approval` is true it shows the review box. If `guardrail_allowed` is false it shows the error.
- `static/style.css` is only appearance.

`thread_id` is stored in the browser so a later approval continues the same Postgres thread.

### Other files

- `requirements.txt` is the package list installed into the `travle` environment.
- `Dockerfile` is the container build. It is separate from local `python app.py`.
- `tools/flight_tool.py` and `tools/travily_tool.py` are older direct API helpers. The live agents use MCP instead.
- `mcp_client_test.py` and `test.py` are manual experiments, not used by the website.

## Why prompts are shortened

Groq’s on-demand plan for the larger model allows 8,000 tokens per minute. A raw Tavily hotel page plus flights, weather, and budget in one prompt can pass that. `_clip` keeps each section short before the model sees it. The full tool text is not stored as a document collection, and this project does not use retrieval (RAG). The data is fetched live for the trip you just asked for.
