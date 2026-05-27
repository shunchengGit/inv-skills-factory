## ADDED Requirements

### Requirement: Load user preferences
The system SHALL load scheduling preferences from `custom-skills/general/daily-arrange/preferences.md`, including working hours, break times, and calendar filter rules.

#### Scenario: Preferences file exists
- **WHEN** daily-arrange starts and `preferences.md` exists
- **THEN** system reads working hours, break slots, and filter rules from the file

#### Scenario: Preferences file missing
- **WHEN** daily-arrange starts and `preferences.md` does not exist
- **THEN** system uses defaults: work 09:00-20:00, lunch 12:00-13:30, evening break 18:00-19:00, no calendar filter

### Requirement: Filter non-actionable calendar events
The system SHALL exclude DingTalk calendar events whose title starts with `[提醒]` from the daily schedule, treating them as reminders rather than fixed time commitments.

#### Scenario: Calendar has a reminder event
- **WHEN** DingTalk calendar returns an event with summary `[提醒] 提交周报`
- **THEN** system excludes it from fixed time blocks and does not display it in the schedule

#### Scenario: Calendar has a normal event
- **WHEN** DingTalk calendar returns an event with summary `项目评审会`
- **THEN** system includes it as a fixed time block in the schedule

### Requirement: Respect working hours and breaks
The system SHALL only schedule tasks within configured working hours and SHALL NOT schedule tasks during configured break periods.

#### Scenario: Task scheduling respects lunch break
- **WHEN** system arranges tasks and the time cursor reaches 12:00
- **THEN** system skips to 13:30 before scheduling the next task

#### Scenario: Task scheduling respects evening break
- **WHEN** system arranges tasks and the time cursor reaches 18:00
- **THEN** system skips to 19:00 before scheduling the next task

#### Scenario: No tasks scheduled before work starts
- **WHEN** the first available time slot is before 09:00
- **THEN** system does not schedule tasks before 09:00

#### Scenario: No tasks scheduled after work ends
- **WHEN** all remaining free slots end after 20:00
- **THEN** system lists unscheduled tasks in an "待排" section

### Requirement: Load routines from daily-arrange config
The system SHALL read fixed daily and weekly routines from `custom-skills/general/daily-arrange/routines.md`, with each routine having a specific start time and duration.

#### Scenario: Daily routine on a weekday
- **WHEN** today is a weekday and `routines.md` defines "晨间阅读" at 07:00 for 60min
- **THEN** system places "晨间阅读" as a fixed block at 07:00-08:00

#### Scenario: Weekly routine matches today
- **WHEN** today is Monday and `routines.md` defines "周会" on 周一 at 09:00 for 60min
- **THEN** system places "周会" as a fixed block at 09:00-10:00

#### Scenario: Weekly routine does not match today
- **WHEN** today is Tuesday and `routines.md` defines "周会" only on 周一
- **THEN** system does not include "周会" in today's schedule

### Requirement: Fetch todo task pool
The system SHALL obtain the full task pool by running `python3 custom-skills/general/todo/scripts/todo.py init` and extracting the `tasks` object grouped by section.

#### Scenario: Successful todo fetch
- **WHEN** `todo.py init` returns `{"success": true, "tasks": {"high": [...], "important_not_urgent": [...], ...}}`
- **THEN** system extracts tasks grouped by priority section for scheduling

#### Scenario: Todo fetch fails
- **WHEN** `todo.py init` returns `{"success": false}` or the command fails
- **THEN** system falls back to reading `~/.todo/TODO.md` directly, parsing sections locally

### Requirement: Fetch calendar events
The system SHALL fetch today's calendar events using `dws calendar event list --start <today>T00:00:00+08:00 --end <tomorrow>T00:00:00+08:00 --format json`.

#### Scenario: Calendar has events
- **WHEN** dws returns a list of calendar events
- **THEN** system extracts summary, start, end, and location for each event, filtering out `[提醒]` prefixed events

#### Scenario: Calendar is empty
- **WHEN** dws returns an empty list
- **THEN** system proceeds with only routines and tasks in the schedule

### Requirement: Arrange tasks into free time slots
The system SHALL compute free time slots between fixed blocks (calendar events + routines + breaks) and fill them with tasks from the todo pool in priority order: high > important_not_urgent > deferred.

#### Scenario: Free slot fits a task
- **WHEN** a free slot of 90 minutes exists and the next pending high-priority task is estimated at 60 minutes
- **THEN** system assigns the task to that slot and reduces remaining slot duration by 60 minutes

#### Scenario: Free slot too small
- **WHEN** all remaining free slots are shorter than 30 minutes
- **THEN** system stops scheduling and lists remaining tasks in "待排"

#### Scenario: Task pool exhausted
- **WHEN** all pending tasks have been scheduled and free slots remain
- **THEN** system leaves remaining slots empty

### Requirement: Estimate task duration
The system SHALL estimate each task's duration at 60 minutes by default, or 30 minutes if the task content suggests a quick action (keywords: 回复、检查、确认、提交).

#### Scenario: Standard task
- **WHEN** task content is "完成Q2季度报告"
- **THEN** system estimates duration as 60 minutes

#### Scenario: Quick task
- **WHEN** task content contains "回复邮件" or "确认进度"
- **THEN** system estimates duration as 30 minutes

### Requirement: Output formatted daily plan
The system SHALL output the arranged daily plan in a structured format with sections for calendar events, routines, scheduled tasks, and unscheduled tasks.

#### Scenario: Complete daily plan
- **WHEN** all data sources are loaded and arrangement is complete
- **THEN** system outputs: header with date/weekday, calendar events section, routines section, scheduled tasks with time slots and priority markers, and unscheduled tasks if any

### Requirement: Week mode
The system SHALL support a week mode that fetches 7 days of calendar events, loads the task pool once, and outputs daily plans for all 7 days with weekly routines matched by weekday.

#### Scenario: Week overview
- **WHEN** user requests a week view
- **THEN** system fetches calendar for Monday through Sunday, loads task pool once, and outputs 7 daily plans with weekly routines distributed by weekday
