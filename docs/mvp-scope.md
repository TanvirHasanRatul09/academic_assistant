# Milestone 0: MVP scope and decisions

Status: complete for design purposes; provider limits must be revalidated before production.

## MVP

The first release is a privacy-conscious, read-only academic dashboard for one authenticated student. It will sign in with Google; collect section, lab group, timezone, selected courses, and notification preferences; synchronize permitted Google Classroom courses and stream content; normalize assignments, announcements, materials, deadlines, and the student's own submission state; filter items by course/section/group; show source links, sync time, and extraction confidence; maintain local read/acknowledged/complete state; and provide responsive desktop/mobile views with an offline read-only cache.

Classroom data remains authoritative. Local completion and acknowledgement state never modifies Classroom.

## Deferred

Teacher/admin workflows, creating or editing Classroom content, grade changes, roster management, Drive file ingestion, browser push, AI chat, multi-provider integrations, advanced change notifications, and automatic action-taking are deferred because they require broader permissions or additional review.

## Ownership

Google owns identity and Classroom source records. The application owns normalized copies, derived classifications, local task state, sync metadata, audit records, and account/profile settings. A user may view only records linked to their authenticated internal user ID.

