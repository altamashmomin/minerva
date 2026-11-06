# Collaboration Protocol

## Roles
- Alta: relays between the AIs and holds final authority on anything left unresolved.
- Claude and ChatGPT: draft and review in turns.

## Source of truth
This repository. Neither AI's conversational memory is a dependency. Each turn starts by reading `HANDOFF.md` and ends by updating it.

## Four-turn review, per work package section
1. Turn 1: one AI drafts, in `proposed/<wp>/`.
2. Turn 2: the other reviews and revises, in `proposed/<wp>/`.
3. Turn 3: the first revises in reply.
4. Turn 4: consensus, as an acceptance record per finding: Agree, Agree with limitation, Disagree (Alta decides), Deferred. No fifth turn.

## Rules for each turn
- At most 7 ranked findings; say what to keep.
- Full files every turn, not fragments.
- No scope growth. Extras go to the parking list in `HANDOFF.md`.
- Each section stays near 200 lines of code.

## Proposed versus accepted
- Work in progress lives only in `proposed/`.
- Code moves to `accepted/` only after Turn 4 and Alta's sign-off, with tests passing.

## Every completed review produces
1. An accepted code checkpoint: files copied to `accepted/<wp>/`, committed, tagged `wpN-accepted-vX`.
2. A brief decision record in `decisions/` and a line in `DECISIONS.md`.
3. An updated `HANDOFF.md`.
