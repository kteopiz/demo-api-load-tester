# Canadian Weather Workload Generator

This portfolio project is a generalized adaptation of an API load-testing CLI I owned during my time at Environment and Climate Change Canada.

Four new weather features depended on an experimental internal API. Each feature requested its own set of weather parameters, and those requests could target any latitude and longitude in Canada. As the API team encountered slow response times, they and project managers needed a repeatable way to test the API against the specific requests those features would make.

I built the CLI to generate those workloads for Siege, combining feature-specific request profiles with repeated locations and randomly sampled coordinates across a Canadian bounding box. This made it possible to run load tests repeatedly using the same kinds of requests the application sent.

The proportion of requests assigned to each feature was configurable. Before launch, we had no usage data, so the initial weights reflected our best estimates. After the first week of launch, we analyzed web usage and adjusted the weights to reflect how people actually used the features. The workload could evolve from an assumed traffic mix to one informed by observed behavior.

This version preserves that approach using a fictional API contract, illustrative workload weights, and synthetic location data. It is a personal portfolio demonstration, not an official or endorsed Environment and Climate Change Canada project, and it does not produce real forecasts.

The generator uses Python's standard library and writes a Siege request file without making network requests. An optional local mock API lets you run the full workflow with synthetic responses.

## Quick start

Requires Python 3.9 or later. Siege is optional and needed only to execute the generated workload.

```sh
# Generate 100 requests with reproducible sampling
python3 main.py --requests 100 --cached-percent 20 --hours 24 --seed 42

# Inspect the generated request file
head -n 2 data/urls.siege

# Start the optional local demo API (leave running)
python3 mock_api.py
```

In another terminal:

```sh
curl http://localhost:8000/health
siege -c5 -t10S -f data/urls.siege --content-type 'application/json' -H 'Accept: application/json'
```

Use Ctrl-C to stop the demo server. It binds only to the local machine. It returns deterministic synthetic values and does not implement caching or emulate a production service. Siege results measure this local Python mock and the host machine, not a real weather backend.

## How the workload works

Four profiles request different sets of variables: `feature_1`, `feature_2`, `feature_3`, and `feature_4`. Illustrative default weights are 35%, 30%, 15%, and 20%. Largest-remainder allocation ensures profile counts sum to the requested total, including for small workloads.

The generator chooses exactly `round(requests * cached_percent / 100)` request slots from a synthetic hot-location set. Other slots use random coordinates within the original Canadian bounding rectangle (42–83° N, 141–53° W) and exclude the hot set. This rectangle is not clipped to Canada’s borders, so sampled points can fall in water or outside the country. The synthetic hot locations also lie within these bounds. Slots are selected across the whole workload, so individual profiles need not have the same hot-location proportion. Hot coordinates are sampled uniformly with replacement; a small workload is not guaranteed to repeat a location.

The `--cached-percent` option describes traffic intended to exercise a cache. It does not measure or guarantee cache hits. Both the profiles and final requests are shuffled. A seed reproduces the generated file for the same inputs and Python environment. `feature_4` requests use one hour; other profiles use `--hours`.

## Fictional API contract

`POST /forecast` accepts a payload such as:

```json
{
  "profile": "feature_2",
  "location": { "latitude": 58.75, "longitude": -116.125 },
  "hours": 24,
  "variables": ["temperature", "precipitation", "wind_speed"]
}
```

The mock returns `synthetic: true`, the location and profile, and a `forecast` array with relative hour offsets and requested values. Values use illustrative Celsius, millimeters per hourly interval, kilometers per hour, percent humidity, and hectopascals. There are no real observation times or external data sources. Invalid payloads return HTTP 400; unknown routes return HTTP 404.

## Options and layout

| Option             | Default                        | Purpose                                         |
| ------------------ | ------------------------------ | ----------------------------------------------- |
| `--base-url`       | `http://localhost:8000`        | API base URL; `/forecast` is appended           |
| `--requests`       | `100`                          | Positive number of requests                     |
| `--cached-percent` | `20`                           | Percentage using synthetic hot locations, 0–100 |
| `--hours`          | `24`                           | Forecast length, 1–168                          |
| `--seed`           | Unset                          | Reproducible random sampling                    |
| `--locations`      | `data/synthetic_locations.csv` | CSV with latitude and longitude columns         |
| `--output`         | `data/urls.siege`              | Generated Siege request file                    |

Default file paths are relative to the project directory; explicit paths are relative to the working directory. Generating again overwrites the selected output file. Run workloads only against a target you are authorized to test.

- `main.py`: CLI, exact request allocation, and workload assembly.
- `config/params.py`: fictional variable sets per profile.
- `config/weights.py`: illustrative profile proportions.
- `config/bounds.py`: Canadian random-sampling bounds and coordinate precision.
- `utils/coords.py`: CSV validation and coordinate generation.
- `utils/urls.py`: Siege serialization.
- `data/synthetic_locations.csv`: synthetic hot locations without traffic counts.
- `mock_api.py`: optional local forecast service.
- `tests/test_demo.py`: allocation, reproducibility, serialization, and HTTP checks.

## Checks

```sh
python3 -m unittest discover -s tests -v
```

The demo has no third-party Python dependencies. The mock is a demonstration server, not a production deployment or a representative performance benchmark.
