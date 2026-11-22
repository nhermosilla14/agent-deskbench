# Capture waits for a viewable window, then for a still frame

- Status: Accepted
- Date: 2026-11-22
- Deciders: Nicolás Hermosilla Polanco
- Approved by: Nicolás Hermosilla Polanco
- Spec area: cli.md

## Context

Measured on the real bench: a screenshot taken one second after launching a window is a uniform
black image, because the window is not mapped yet. By three seconds it is drawn. Nothing about the
image tells the caller which case they got, so an agent either adds sleeps it cannot tune or
concludes the application is broken.

Waiting for the frame to stop changing is not enough on its own: before the window appears the
screen is perfectly still and perfectly black.

## Decision

`shot` runs a helper inside the container that waits on two conditions in order:

1. at least one client window is `IsViewable` according to the window manager, or the wait budget
   is exhausted;
2. the root window's contents are unchanged for `--settle` milliseconds (default 250), or the
   budget is exhausted.

Only then does it capture, and it always captures rather than failing. The whole wait is bounded at
6 s, with at most 2.5 s spent hoping for a window, so an empty desktop answers in about three
seconds and an animated screen still returns.

A managed window is not a painted window: the window manager lists a client well before its pixels
appear, and the screen is perfectly still in between. The entrypoint therefore records a reference
fingerprint of the empty desktop at start-up, and phase 2 waits until the screen differs from it.

Measurement that shaped this: the **first** X client in a fresh container took 5–7 s to paint, while
the second took 11 ms — a one-off initialisation cost (client start-up and font caches) that every
first screenshot would otherwise race against. The entrypoint now pays it during start-up with a
throwaway client, and records the reference frame afterwards. The first real screenshot then costs
about 0.8 s instead of 7 s.

## Alternatives considered

- **Sleep in the caller** — untunable, and the skill had to warn about it; a fixed sleep is either
  slow or wrong.
- **Wait for stillness only** — cannot distinguish "not drawn" from "nothing to draw".
- **Screenshot diffing on the host** — more round trips and more code for the same answer.

## Consequences

`shot` takes ~0.4 s on a static screen and up to 3 s on an empty or animated one. A genuinely black
application is indistinguishable from an undrawn one, so the tool cannot promise the frame contains
the app — only that a window existed and the screen had settled.
