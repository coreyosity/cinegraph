"""Taste-model CLI — leave-one-out backtest / weight tuning over the vault's rated films.
The model itself lives in `core.taste` (vault-free); this just loads films and feeds it.

    python scripts/taste.py --vault vault --backtest      # accuracy report
    python scripts/taste.py --vault vault --tune          # grid-search the blend weights
"""

from __future__ import annotations

import argparse
from pathlib import Path

import common
from core import taste


def main() -> int:
    parser = argparse.ArgumentParser(description="Taste model — backtest / tune.")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()

    films = [f for f in common.load_films(args.vault) if f.rating is not None]
    weights, k = taste.DEFAULT_WEIGHTS, taste.SHRINK
    if args.tune:
        weights, k, r, mae = taste.tune(films)
        print(f"Best: weights={weights} shrink={k}  (r={r:.3f}, MAE {mae:.3f})")
    if args.backtest or not args.tune:
        r = taste.backtest(films, weights, k)
        lift = 100 * (1 - r["mae"] / r["base_mae"])
        print(f"Backtest on {r['n']} rated films (baseline ★{r['baseline']}):")
        print(f"  MAE  {r['mae']:.3f}★   RMSE {r['rmse']:.3f}★   correlation r={r['r']:.3f}")
        print(f"  vs naive (always ★{r['baseline']}): MAE {r['base_mae']:.3f}★  →  {lift:.0f}% better")
        worst = sorted(r["rows"], key=lambda x: abs(x[0] - x[1]), reverse=True)[:6]
        print("  most surprising to the model (predicted vs actual):")
        for p, a, t in worst:
            print(f"    {p:.1f} → {a:.1f}   {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
