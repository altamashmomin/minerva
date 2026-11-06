# MINERVA: Project Context

## Goal
A local, private home assistant that grows in stages. Version 0.1 (Ledger-mind) categorizes Ledger transactions on a Raspberry Pi 5 inference node, with Claude Haiku as fallback, without touching the production Ledger Pi.

## Milestones
- 0.1 Ledger-mind: rules baseline, evaluation harness, local model benchmark, shadow integration.
- 0.2 Local knowledge (hardware gate).
- 0.3 Voice and dashboard.
- 0.4 Sensors.
- 1.0 Appliance.

## 0.1 work packages
WP1 dataset export, WP2 rules baseline, WP3 evaluation harness, WP4 benchmark runner, WP5 scoring experiment, WP6 inference service, WP7 shadow integration, WP8 measurement, WP9 write-up.

## Current state (2026-11-06)
- Design frozen (Ledger-mind proposal v0.3). Work plan approved with amendments.
- WP2/WP3: accepted 2026-11-06 as a synthetic-data evaluation baseline (`wp2-wp3-accepted-v1`).
- Next: WP1 dataset export, pending Alta's go-ahead.

## Standing constraints
- Nothing is installed on the production Ledger Pi.
- Alta types the code, so each section stays near 200 lines.
- This repo, not any AI's chat memory, is the source of truth.
