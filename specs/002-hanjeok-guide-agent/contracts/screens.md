# Contract: Screens

What each screen shows in each state. A state listed here has a test that
renders it from a fixture. All routes sit under the existing `[lang]` segment.

## Design values

Components use purpose-named values only (FR-033, SC-011). The names, grouped:

| Group | Names |
| --- | --- |
| Surface | `surface-canvas`, `surface-panel`, `surface-subtle`, `surface-inverse`, `surface-scrim` |
| Text | `text-title`, `text-body`, `text-muted`, `text-disabled`, `text-inverse` |
| Line | `line-normal`, `line-strong` |
| Brand | `brand-primary`, `brand-pressed`, `brand-soft`, `accent-route`, `accent-quiet`, `accent-sky`, `accent-gold` |
| Grade | `grade-{relaxed,normal,crowded,very-crowded}-{soft,text,fill}`, `grade-unknown-{soft,text}` |
| Status | `status-{info,success,warning,danger}-{soft,text}` |
| Citation | `cite-record-{soft,text}`, `cite-policy-{soft,text}` |
| Type | `display`, `title-1`, `title-2`, `body`, `body-strong`, `caption`, `mono` |
| Shape | `radius-card`, `radius-control`, `radius-chip`; control heights 44, 48, 56 |

Every colour name has a light and a dark value. `grade-unknown` exists so "no
data" is never drawn with a grade's colour (FR-014).

## Character

One still pose per state. The image is decorative; the state is always also in
text beside it with the next action (FR-035).

| State | Pose | Shown when | Text beside it says |
| --- | --- | --- | --- |
| `waiting` | Resting on the ground, looking up | No question yet | What can be asked, with examples |
| `looking` | In flight, leaning forward | A step is running | Which step is running |
| `found` | Landed, holding out a small card | Answer shown | Nothing extra; the answer is the text |
| `choose` | Holding two cards, head tilted | `ask_user` | The prompt and the candidates |
| `no-data` | Empty hands, looking at them | `declined`, `no_grounds`, or a step with `no_data` | What is not known and what can be asked instead |
| `failed` | Sitting, wing drooped | `failed` | What went wrong and how to retry |

Movement, if any, begins from the still pose and is removed under
`prefers-reduced-motion` (FR-036). The character is never a button.

## `/[lang]/ask`

| State | Shows |
| --- | --- |
| Empty | Character `waiting`, question field, four example questions as chips, the refresh time of the data |
| Running | The question, a step list growing in order with each step's name, inputs summary and status; character `looking`; the field disabled |
| Answered | Step list collapsed to a summary line that reopens, the answer, citation chips in two visibly different kinds (record, policy), a "show path" control, the follow-up field |
| Partial | As answered, with a notice that lookups were cut short |
| Ask user | Character `choose`, the prompt, candidates as buttons; choosing one resumes the question |
| Declined / no grounds | Character `no-data`, the message, example questions |
| Failed | Character `failed`, the message, a retry control |
| Usage limit | The message and when to come back |
| Stream cut | The steps received, a notice that the connection dropped, a retry control |

A citation chip opens a sheet: a record shows its fields and fetch time; a
policy document shows the page. The existing `CitationSheet` behaviour (Esc,
backdrop, focus on close) is reused.

Follow-up questions append below; earlier answers stay readable.

## `/[lang]/graph`

| State | Shows |
| --- | --- |
| From an answer | The path for that answer: start place centred, related places around it in rank order with rank labels, region and documents as separate groups; edges labelled by kind. Exactly what the `path` event carried (FR-022) |
| Browsing | A name search field, results, and on selecting a place its neighbourhood from `GET /guide/places/{id}` |
| Place selected | A side panel: name, region, category, overview, "congestion: ask a question to check" when covered, "no congestion data" when not |
| Not found / unavailable | Message; no empty graph drawn |

The same data is also given as a list below the drawing, so the view is usable
without reading the drawing and at phone width, where the list comes first.

## `/[lang]/eval`

| State | Shows |
| --- | --- |
| Report | Provenance line (data refresh, question set revision, model, recording time); a table of metrics by strategy, every cell with its sample count; forbidden behaviours with runs and occurrences; results by question kind; the statement of what was held identical; limitations |
| Not scored | The cell reads "not scored" with the reason, never `0` (Story 3, scenario 2) |
| Sample | Question, each strategy's answer or cause, steps, supplied passages, scores |
| No report | A sentence saying no evaluation has been published; no table |

Numbers are text in a table. No chart is drawn: two strategies and a handful
of metrics read faster as a table, and a chart would hide the sample counts.

## `/[lang]/design`

The design values rendered as swatches and type samples in both appearances,
the shared components in each state, and the six character poses with their
state names. This page is how SC-010 and SC-011 are checked.

## Existing screens

`/[lang]`, `/[lang]/course/[uuid]` and `/[lang]/evidence` keep their behaviour
and their Korean strings, which existing tests match literally. They move to
the design values. The home page gains one entry point to `/[lang]/ask`.

## Language

New chrome strings are added to both `ko` and `en` in `lib/i18n.ts`; the type
of `en` is derived from `ko`, so a missing translation fails typecheck. Answers
and data stay Korean in both.

## Width and contrast

Every state above is laid out at 360px wide and at desktop width. Text on its
background meets 4.5:1 in both appearances, checked for each colour pair on
the design page (FR-038).
