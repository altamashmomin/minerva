# MINERVA 0.1: Accepted Architecture

Source: Ledger-mind proposal v0.3 (frozen). Changes need a decision record.

## Nodes
- Ledger Pi (production): unchanged except a feature-flagged client in WP7.
- Inference Pi (Raspberry Pi 5, 8 GB): Ollama + FastAPI service, reached over Tailscale with token auth.

## Pipeline
1. Rules first (WP2). Unanimous merchant history, MIN_HISTORY = 3, else abstain with a reason code.
2. Local model (gemma3:1b, qwen3:1.7b, qwen3:4b; Qwen3 non-thinking; Q4 then Q5), chosen by WP4.
3. Claude Haiku fallback.
Ledger owns the acceptance policy. Rollout runs in shadow mode first.

## Contracts
- `Prediction(category_id: str | None, reason_code: str)`; None means abstain.
- Stable category IDs. Experimental score returns null when unreliable.
- `POST /v1/infer`; deadlines 5 s interactive, about 30 s background; idempotency and circuit breaker added at integration.

## Evaluation
- Temporal split and merchant-grouped hash split, for rules and models alike. Lookups built from train only.
- Metrics: coverage, precision with Wilson 95% interval, false acceptance = wrong/accepted, wrong/all, oracle upper bound (labeled as such).
- An untouched holdout set is kept for the final comparison.
