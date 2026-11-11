# Triage Labels

The skills speak in terms of five canonical triage roles. This repo tracks issues as markdown files under `.scratch/`, so there is no server to create a label on: a role is a string attached to the ticket, written twice for two different readers.

| Role in mattpocock/skills | string in our tracker | Meaning                                  |
| -------------------------- | --------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`        | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`          | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`     | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`     | Requires human implementation            |
| `wontfix`                  | `wontfix`             | Will not be actioned                     |

The string ends up in two different places, and they do different jobs:

- `<!-- DSH-LABELS: … -->` in the hidden header block is what `deck_issue_list` filters by and what `deck_issue_patch` writes. A role recorded only on the visible line is invisible to every label query.
- The visible `**Status:** …` line under the title is what a human reads when opening the file, and it is what decides open vs closed. Closing values are `resolved`, `completed`, `closed` and `done` (the deck lowercases the line and compares); any other value leaves the ticket open. Tickets written by the deck itself use `resolved`, older hand-written ones in this repo use `done` — both close.

So applying a role means setting both. `claimed` and `resolved` are not triage roles: they are wayfinder/ticket lifecycle values and belong on the `Status:` line alone.

[`docs/agents/label-colors.yaml`](label-colors.yaml) is the deck's colour table for these names; it needs a row only when a name becomes permanent.

Edit the middle column to match whatever vocabulary you actually use.
