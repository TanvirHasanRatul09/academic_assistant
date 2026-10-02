# Google Classroom access decision

Checked against the Google Classroom API documentation on 2026-09-21. Recheck scopes and eligibility before production verification.

## Student resources used by the MVP

The student read path uses courses the student can access; announcements; `CourseWork` assignments/questions and due information; `CourseWorkMaterial` items and topics; attachments and trusted source URLs where metadata is available; and the current student's `StudentSubmission` metadata when permitted. `CourseWorkMaterial` has no due date or student submission. Attachments may have incomplete metadata when the student lacks access to the underlying resource.

The client must use pagination, partial response fields, bounded retries, and the authenticated student's permissions. It must not assume every domain enables every resource or that every attachment is readable.

## Minimum planned scopes

```text
openid
email
profile
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/classroom.announcements.readonly
https://www.googleapis.com/auth/classroom.coursework.me.readonly
https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly
https://www.googleapis.com/auth/classroom.topics.readonly
```

The `courses.courseWork.studentSubmissions.list` endpoint accepts `classroom.coursework.me.readonly`, so a separate `classroom.student-submissions.me.readonly` scope is not required for the planned read path. Do not request teacher/admin, roster, write, push-notification, Drive, or Classroom profile email/photo scopes for the MVP.

OAuth consent text must explain that access is read-only and used to organize the student's classes and assignments. Tokens stay on the backend.

## Verification assumptions

The first integration spike must test a student account in a controlled Google Workspace for Education test domain, including archived courses, missing attachments, no due date, restricted content, and revoked access. Behavior also depends on domain policy, license type, quotas, and OAuth verification.

References: [Classroom API resources](https://developers.google.com/workspace/classroom/guides/key-concepts/api-structure), [OAuth scopes](https://developers.google.com/workspace/classroom/guides/auth), [student permissions](https://developers.google.com/workspace/classroom/guides/key-concepts/user-types), [student-submission list scopes](https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWork.studentSubmissions/list).
