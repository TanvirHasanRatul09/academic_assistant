# In-app notification rules

Academic Assistant creates in-app notifications only during a successful or partial Google Classroom synchronization.

## Creation rule

A newly inserted Classroom item creates one notification when all conditions are true:

1. The derived task belongs to the authenticated user and is relevant to that user.
2. The task is not complete.
3. The extraction marks it as action required.
4. Its event type is assignment, exam, or notice.
5. Its priority is at or above the user's minimum.
6. The event type is enabled.
7. The course is enabled.

Materials, generic posts, non-actionable notices, irrelevant section/group items, completed tasks, and low-priority items are suppressed.

“New” means the Classroom item was first inserted during the current sync. Existing historical items do not generate a notification merely because Milestone 8 was enabled.

## Deduplication

The database permits only one notification for a user, task, and notification kind. Repeating a sync or rerunning extraction therefore does not duplicate an alert.

## User controls

The notification center supports:

- unread count;
- individual and bulk mark-read actions;
- dismiss;
- links to the related dashboard task and original HTTPS Classroom item;
- assignment, exam, and notice toggles;
- minimum priority from low through high;
- per-course enable/disable settings.

Read and dismissed state is user-scoped and does not modify Google Classroom data.

## Browser push decision

Browser push is deferred. In-app rules and alert quality should be observed in normal use before adding permission prompts, subscriptions, lock-screen previews, or another delivery channel. This avoids unnecessary permission requests and privacy exposure.
