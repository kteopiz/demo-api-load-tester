#!/usr/bin/env python3
"""Generate synthetic weather workloads without making network requests."""
import argparse
import math
from pathlib import Path
import random
from urllib.parse import urlsplit

from config.params import PROFILES
from config.weights import PROFILE_WEIGHTS
from utils.coords import generate_random_coords, load_cached_coords
from utils.urls import generate_urls

ROOT = Path(__file__).resolve().parent


def allocate_counts(total, weights):
    """Largest-remainder allocation preserves totals even for tiny workloads."""
    if not weights or any(not math.isfinite(w) or w < 0 for w in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Profile weights must be finite, nonnegative, and have a positive sum")
    quotas = {key: total * weight / sum(weights.values()) for key, weight in weights.items()}
    counts = {key: math.floor(quota) for key, quota in quotas.items()}
    order = sorted(quotas, key=lambda key: quotas[key] - counts[key], reverse=True)
    for key in order[:total - sum(counts.values())]:
        counts[key] += 1
    return counts


def build_workload(total, cached_percent, hours, cached_coords, rng):
    if total <= 0 or not 0 <= cached_percent <= 100 or not 1 <= hours <= 168:
        raise ValueError("Requests must be positive; hours must be 1–168; cached percent must be 0–100")
    if set(PROFILES) != set(PROFILE_WEIGHTS):
        raise ValueError("Profiles and weights must have matching keys")
    if not cached_coords:
        raise ValueError("At least one hot location is required")
    counts = allocate_counts(total, PROFILE_WEIGHTS)
    profiles = [profile for profile, count in counts.items() for _ in range(count)]
    rng.shuffle(profiles)
    # Select hot slots globally: no profile can receive more than its capacity.
    hot_count = round(total * cached_percent / 100)
    hot_slots = set(rng.sample(range(total), hot_count))
    hot_set = set(cached_coords)
    requests = []
    for index, profile in enumerate(profiles):
        if index in hot_slots:
            lat, lon = rng.choice(cached_coords)
        else:
            for _ in range(10000):
                lat, lon = generate_random_coords(rng)
                if (lat, lon) not in hot_set:
                    break
            else:
                raise ValueError("Unable to sample a location outside the hot set")
        requests.append({"profile": profile, "location": {"latitude": lat, "longitude": lon},
                         "hours": 1 if profile == "feature_4" else hours,
                         "variables": PROFILES[profile]})
    rng.shuffle(requests)
    return requests, counts, hot_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--cached-percent", type=int, default=20,
                        help="Percent sampled from synthetic hot locations; does not prove server cache hits")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--locations", type=Path, default=ROOT / "data/synthetic_locations.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/urls.siege")
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment
            or parsed.username or parsed.password or any(c.isspace() for c in args.base_url)):
        parser.error("Base URL must be an HTTP(S) URL without credentials, whitespace, query, or fragment")
    try:
        coords = load_cached_coords(args.locations)
        requests, counts, hot_count = build_workload(args.requests, args.cached_percent, args.hours, coords, random.Random(args.seed))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(generate_urls(requests, args.base_url)) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print("Profile counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print(f"Hot-location requests: {hot_count}/{len(requests)} ({hot_count / len(requests):.1%})")
    print(f"Wrote {len(requests)} requests to {args.output}; no network requests made.")


if __name__ == "__main__":
    main()
