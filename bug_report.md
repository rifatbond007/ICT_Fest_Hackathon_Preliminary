# Bug Report — CoWork API

## Bug 1: UTC Offset Not Normalized (Easy)
- **File:** `app/timeutils.py:11-13`
- **What:** `parse_input_datetime` stripped the timezone info with `.replace(tzinfo=None)` without first converting to UTC. Example: `18:00:00+06:00` was stored as `18:00:00` instead of `12:00:00` UTC.
- **Fix:** Added `.astimezone(timezone.utc)` before stripping tzinfo, so offset-carrying inputs are properly normalized to UTC.

## Bug 2: Token Revocation Checked Wrong Claim (Easy)
- **File:** `app/auth.py:97`
- **What:** The revocation set stores the `jti` claim (line 86), but line 97 checked `payload.get("sub")` instead of `payload["jti"]`. Since `sub` is a user ID (never added to the set), the check was always False — revoked tokens were never actually rejected.
- **Fix:** Changed `payload.get("sub")` to `payload["jti"]`.

## Bug 3: Grace Window in `start_time` Check (Easy)
- **File:** `app/routers/bookings.py:86`
- **What:** The original check was `start <= now - timedelta(seconds=300)`, granting a 5-minute grace window for past start times. Business rule #2 requires "strictly in the future — no grace window."
- **Fix:** Changed to `start <= now`.

## Bug 4: Overlap Check Used Wrong Operator (Easy)
- **File:** `app/routers/bookings.py:50`
- **What:** Conflict check used `b.start_time <= end and start <= b.end_time`. This incorrectly flagged back-to-back bookings (where `end == b.start_time`) as conflicts. Business rule #3 says "Back-to-back bookings are allowed."
- **Fix:** Changed to `b.start_time < end and start < b.end_time`.

## Bug 5: Pagination — Wrong Sort, Offset, and Hardcoded Limit (Medium)
- **File:** `app/routers/bookings.py:137-139`
- **What:**
  - Sort was descending (`start_time.desc()`) instead of ascending per rule #11.
  - Offset was `page * limit` instead of `(page - 1) * limit`, causing page 2 to skip the first `limit` items.
  - Limit was hardcoded to `10` instead of using the `limit` parameter.
- **Fix:** Changed to ascending sort, correct offset formula, and variable limit.

## Bug 6: Booking Detail Returned Wrong `start_time` (Easy)
- **File:** `app/routers/bookings.py:166`
- **What:** `response["start_time"]` was set to `iso_utc(booking.created_at)` (creation timestamp) instead of `iso_utc(booking.start_time)` (the actual booking start time).
- **Fix:** Changed to `booking.start_time`.

## Bug 7: Refund Tiers — Wrong Comparisons and Fallback (Medium)
- **File:** `app/routers/bookings.py:200-206`
- **What:**
  - `notice_hours` was computed as `int(notice.total_seconds() // 3600)`, then line 203 compared `notice >= timedelta(hours=24)` (a timedelta vs int comparison that is always True in Python 3), making the `elif` branch always execute.
  - The `< 24h` fallback gave `refund_percent = 50` instead of `0`.
  - The check for ≥48h used `> 48` instead of `>= 48`.
- **Fix:** Made `notice_hours` a float, used `notice_hours >= 48` and `notice_hours >= 24`, and set the fallback to `0`.

## Bug 8: Duplicate Username Returned 200 Instead of 409 (Medium)
- **File:** `app/routers/auth.py:37-43`
- **What:** When a duplicate username existed in the same org, the code returned the existing user's data with HTTP 201 (status_code from the decorator). Per rule #15, duplicate username should return `409 USERNAME_TAKEN`.
- **Fix:** Replaced the return with `raise AppError(409, "USERNAME_TAKEN", ...)`.

## Bug 9: Admin Booking List Only Showed Own Bookings (Medium)
- **File:** `app/routers/bookings.py:134`
- **What:** The base query filtered by `Booking.user_id == user.id` unconditionally, so admins could only see their own bookings instead of all bookings in their org (rule #10).
- **Fix:** Added an org-join filter and conditionally applied user filter only for non-admin users.

## Bug 10: Missing Minimum Duration Check (Easy)
- **File:** `app/routers/bookings.py:93`
- **What:** Only `> MAX_DURATION_HOURS` was checked, but `MIN_DURATION_HOURS` (1) was never enforced. Zero or sub-hour durations were accepted.
- **Fix:** Added `duration_hours < MIN_DURATION_HOURS` to the bounds check.

## Bug 11: Availability Cache Not Invalidated on Cancel (Medium)
- **File:** `app/routers/bookings.py:217`
- **What:** Only `invalidate_report` was called on cancel. The availability cache remained stale, serving old busy intervals after a booking was cancelled.
- **Fix:** Added `cache.invalidate_availability(booking.room_id, booking.start_time.date().isoformat())`.

## Bug 12: Refund Amount Truncated Instead of Rounded Half-Up (Medium)
- **File:** `app/services/refunds.py:15-17`
- **What:** The formula `dollars = price_cents / 100.0; refund_dollars = dollars * percent / 100; int(refund_dollars * 100)` converted to dollars and back, losing precision via truncation. The spec requires "nearest cent, half-cents rounding up" (e.g. 50% of 1001 = 501).
- **Fix:** Changed to direct cents formula `int(price_cents * percent / 100.0 + 0.5)` and made the function accept an optional pre-computed `amount_cents` parameter to guarantee consistency with the cancellation response.

## Bug 13: Reference Counter Race Condition (Hard)
- **File:** `app/services/reference.py`
- **What:** `_counter["value"]` was read, then (after a sleep) incremented and written. Under concurrent requests, two threads could read the same value, producing duplicate reference codes.
- **Fix:** Added `threading.Lock()` to protect the read-increment-write cycle.

## Bug 14: Rate Limiter Race Condition (Hard)
- **File:** `app/services/ratelimit.py`
- **What:** Bucket list was read, filtered, then (after a sleep) appended. Concurrent requests could bypass the rate limit by both reading before either appended.
- **Fix:** Added `threading.Lock()` to protect the entire bucket read/filter/append/check sequence.

## Bug 15: Stats Counter Race Condition (Hard)
- **File:** `app/services/stats.py`
- **What:** Stats dict was read (with a simulated aggregation pause), then written. Concurrent creates/cancels could lose updates (lost update problem).
- **Fix:** Added `threading.Lock()` to protect the read-modify-write cycle.

## Bug 16: Notification Lock Order Inversion (Hard)
- **File:** `app/services/notifications.py`
- **What:** `notify_created` acquired `_email_lock` then `_audit_lock`, while `notify_cancelled` acquired `_audit_lock` then `_email_lock` — a classic lock-ordering deadlock.
- **Fix:** Unified both functions to use the same lock order: `_email_lock` then `_audit_lock`.

## Bug 17: Conflict Check TOCTOU Race (Hard)
- **File:** `app/routers/bookings.py`
- **What:** `_has_conflict` loaded all confirmed bookings, then (after a simulated warmup sleep) checked for overlap. Concurrent booking creations could both pass the conflict check, resulting in double-bookings. Similarly, `_check_quota` counted bookings before the current transaction committed.
- **Fix:** Wrapped the conflict check, quota check, and booking creation in a `threading.Lock()` (`_creation_lock`) to serialize concurrent booking creation for the same room.

## Bug 18: Cancel Race — Multiple Refunds for Same Booking (Hard)
- **File:** `app/routers/bookings.py`
- **What:** Concurrent cancel requests for the same booking could both pass the `status == "cancelled"` check (TOCTOU), each logging a refund and violating "a cancelled booking has exactly one RefundLog entry."
- **Fix:** Wrapped the cancel read/check/write cycle in a `threading.Lock()` (`_cancel_lock`).
