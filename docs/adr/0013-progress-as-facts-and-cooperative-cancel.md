# ADR-0013: Progress as facts, and cancelling by asking

- Status: accepted
- Date: 2026-11-11

## Context

The pipeline reported `(message, fraction)`. Only the fraction of files read was real; the rest were constants chosen to make a bar move (0.70, 0.78, 0.86, 0.93). A bar that fills at an invented pace tells the user nothing, and on a large project it sat at "Tracing request flows" for most of the time. An analysis could not be stopped either: closing the window was the only way out.

## Decision

- The pipeline reports `Progress(stage, done, total, detail)`. Every stage announces that it started; only the stage that reads files has a `total`, because it is the only one that can be counted.
- The app shows the stages as a list, each pending, running or done. The running stage has a spinner; the counted stage also has a bar and says "218 of 462 files". No percentage is shown anywhere.
- `analyse()` takes a `cancelled()` function and polls it at the same points where it reports. When it answers yes, the pipeline raises `Cancelled`. A background task therefore stops between two files or two stages, never in the middle of one, and nothing is left half-written because the analysis writes nothing.
- A task whose result arrives after it was replaced is ignored: the window compares it with the task it is waiting for.

## Consequences

- What the screen says is true at every moment, including "this stage cannot be measured".
- Cancelling is not instant: a stage that takes two seconds delays the stop by up to two seconds. No stage is long enough for that to matter (linking was, until it got an index).
- Callers that add work after the analysis (the app draws the first diagrams) add their own stage with their own words.
