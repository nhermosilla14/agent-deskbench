# Handoff

The one path where the agent stops and a human acts.

## Behaviours

### Request a human
`deskbench ask NAME MESSAGE` notifies the human, tells them which desktop needs attention, and blocks
until they answer, so the agent resumes only after the intervention finished.
- Criteria:
  - The notification carries the desktop name, the message and the viewer URL.
  - It offers *Open viewer* and *I'm done*.
  - While waiting, the tray asks for attention; the marker is removed in every exit path.
  - *I'm done* exits 0; the timeout exits 4; dismissal exits 5.
  - An unknown desktop exits 1 and sends no notification.
- Tests: tests.test_handoff.Handoff.test_timeout_is_reported_and_the_marker_is_cleared, tests.test_handoff.AskArgumentHandling.test_unknown_desktop_does_not_notify

## Not supported

- Chat, audio or video between agent and human.
- Follow-up questions while waiting; one request, one answer.
