# Bug Report — CoWork API

## Bug 1: UTC Offset Not Normalized
- **File:** `app/timeutils.py` lines 11–13
- **What and Why:** `parse_input_datetime` called `.replace(tzinfo=None)` without first converting to UTC. This stripped the timezone object without adjusting the time value, so `18:00:00+06:00` was stored as `18:00:00` instead of `12:00:00 UTC`, violating rule #1.
- **Fix:** Added `.astimezone(timezone.utc)` before `.replace(tzinfo=None)` so the time is converted to UTC before the tzinfo is stripped.

---

## Bug 2: Token Revocation Checked Wrong Claim
- **File:** `app/auth.py` line 97
- **What and Why:** The revocation set stores `jti` values, but the check compared `payload.get("sub")` (the user ID) against the set. Since user IDs are never added to the revocation set, the check was always `False` — logout never actually blocked a token from being reused, violating rule #8.
- **Fix:** Changed `payload.get("sub")` to `payload["jti"]`.

---

## Bug 3: Grace Window in `start_time` Check
- **File:** `app/routers/bookings.py`
- **What and Why:** The check was `start <= now - timedelta(seconds=300)`, which allowed bookings with a start time up to 5 minutes in the past. Rule #2 requires start_time to be strictly in the future with no grace window of any size.
- **Fix:** Changed to `start <= now`.

---

## Bug 4: Overlap Check Used Wrong Operator
- **File:** `app/routers/bookings.py`
- **What and Why:** The conflict check used `b.start_time <= end and start <= b.end_time`. This incorrectly flagged back-to-back bookings (where one ends exactly when the other starts) as conflicts. Rule #3 explicitly allows back-to-back bookings.
- **Fix:** Changed to `b.start_time < end and start < b.end_time` (strict less-than).

---

## Bug 5: Pagination — Wrong Sort, Offset, and Hardcoded Limit
- **File:** `app/routers/bookings.py`
- **What and Why:** Three mistakes in the pagination query: sort was descending instead of ascending (rule #11 requires ascending by `start_time`); offset was `page * limit` instead of `(page - 1) * limit` causing page 1 to skip items; and the limit was hardcoded to `10` ignoring the user-supplied `limit` parameter, causing sequential pages to skip or repeat items.
- **Fix:** Changed to ascending sort, corrected offset to `(page - 1) * limit`, and used the variable `limit` parameter.

---

## Bug 6: Booking Detail Returned Wrong `start_time`
- **File:** `app/routers/bookings.py`
- **What and Why:** `response["start_time"]` was set to `iso_utc(booking.created_at)` — the creation timestamp — instead of `iso_utc(booking.start_time)`. This caused `GET /bookings/{id}` to return the wrong time in the `start_time` field, violating the API contract.
- **Fix:** Changed to `iso_utc(booking.start_time)`.

---

## Bug 7: Refund Tiers — Wrong Comparisons and Fallback
- **File:** `app/routers/bookings.py`
- **What and Why:** Three mistakes: `notice_hours` was truncated with `int()` losing fractional hours; the `elif` branch compared a `timedelta` object against an `int` which is always `True` in Python 3 making the 50% branch always execute; and the `< 24h` fallback returned `refund_percent = 50` instead of `0`. Combined, refund was always 50% regardless of notice period, violating rule #6.
- **Fix:** Made `notice_hours` a float via `.total_seconds() / 3600`, used `notice_hours >= 48` and `notice_hours >= 24` for comparisons, and set the fallback to `0`.

---

## Bug 8: Duplicate Username Returned 201 Instead of 409
- **File:** `app/routers/auth.py`
- **What and Why:** When a duplicate username was found in the same org, the code returned the existing user's data with HTTP 201 instead of raising an error. Rule #15 requires a duplicate username within the org to return `409 USERNAME_TAKEN`.
- **Fix:** Replaced the `return` statement with `raise AppError(409, "USERNAME_TAKEN", "Username already taken in this organization")`.

---

## Bug 9: Missing Minimum Duration Check
- **File:** `app/routers/bookings.py`
- **What and Why:** The duration bounds check only verified `> MAX_DURATION_HOURS` but never checked `< MIN_DURATION_HOURS`. This allowed bookings with zero or negative duration to be accepted, violating rule #2 which requires a minimum of 1 hour.
- **Fix:** Added `duration_hours < MIN_DURATION_HOURS` to the condition: `if duration_hours < MIN_DURATION_HOURS or duration_hours > MAX_DURATION_HOURS`.

---

## Bug 10: Availability Cache Not Invalidated on Cancel
- **File:** `app/routers/bookings.py`
- **What and Why:** On cancellation, only `invalidate_report` was called. The availability cache was not cleared, so `GET /rooms/{id}/availability` continued serving stale busy intervals after a booking was cancelled, violating rule #13 which requires the availability to reflect current state immediately.
- **Fix:** Added `cache.invalidate_availability(booking.room_id, booking.start_time.date().isoformat())` in the cancel handler.

---

## Bug 11: Refund Amount Truncated Instead of Rounded Half-Up
- **File:** `app/services/refunds.py` lines 15–17
- **What and Why:** The formula converted `price_cents` to dollars, multiplied by the percentage, then converted back to cents using `int()` which truncates. This caused incorrect refund amounts — e.g. 50% of 1001 cents returned 500 instead of 501. Rule #6 requires rounding to the nearest cent with half-cents rounding up.
- **Fix:** Changed to the direct cents formula `int(price_cents * percent / 100.0 + 0.5)` and added an optional `amount_cents` parameter so the cancel response and RefundLog always store the same pre-computed value.

---

## Bug 12: Reference Counter Race Condition
- **File:** `app/services/reference.py`
- **What and Why:** The counter was read, then (after a simulated delay) incremented and written back without any lock. Under concurrent requests, two threads could read the same counter value and produce duplicate reference codes, violating rule #7.
- **Fix:** Replaced the in-memory counter with a DB-primary-key-based approach: the booking is flushed to obtain its auto-assigned `id`, then the reference code is set as `CW-{id:06d}`. The DB primary key is guaranteed unique by the database itself.

---

## Bug 13: Rate Limiter Race Condition
- **File:** `app/services/ratelimit.py`
- **What and Why:** The bucket list was read, filtered, then (after a simulated delay) appended without a lock. Concurrent requests could both read the bucket before either appended, allowing multiple requests to bypass the rate limit simultaneously, violating rule #5.
- **Fix:** Added `threading.Lock()` wrapping the entire read/filter/append/check sequence so it is atomic.

---

## Bug 14: Stats Counter Race Condition
- **File:** `app/services/stats.py`
- **What and Why:** The stats dict was read (with a simulated pause), then written back without a lock. Concurrent creates/cancels could overwrite each other's updates (lost update problem). Additionally, the in-memory dict reset to zero on every process restart, diverging from actual DB state and violating rule #14.
- **Fix:** Replaced the in-memory dict entirely with a live DB query using `func.count` and `func.sum` on confirmed bookings. This is always consistent with actual data and requires no locking.

---

## Bug 15: Notification Lock Order Inversion — Deadlock
- **File:** `app/services/notifications.py`
- **What and Why:** `notify_created` acquired `_email_lock` then `_audit_lock` (nested), while `notify_cancelled` acquired `_audit_lock` then `_email_lock`. Two concurrent calls (one create, one cancel) could each hold one lock and wait forever for the other — a classic deadlock, violating rule #16 (liveness).
- **Fix:** Made both functions acquire locks sequentially (not nested) in the same order: `_email_lock` first, released, then `_audit_lock` separately.

---

## Bug 16: Conflict Check TOCTOU Race
- **File:** `app/routers/bookings.py`
- **What and Why:** `_has_conflict` loaded confirmed bookings and checked for overlap outside any lock. Two concurrent booking requests for the same room could both pass the conflict check before either committed, resulting in double-bookings, violating rule #3.
- **Fix:** Wrapped the conflict check, quota check, and booking insert inside `_creation_lock` so concurrent creation requests are fully serialized.

---

## Bug 17: Cancel Race — Multiple Refunds for Same Booking
- **File:** `app/routers/bookings.py`
- **What and Why:** Concurrent cancel requests for the same booking could both pass the `status == "cancelled"` check before either committed the status update, each logging a separate RefundLog entry. Rule #6 requires exactly one RefundLog entry per cancelled booking.
- **Fix:** Wrapped the entire cancel read/check/write cycle inside `_cancel_lock` to serialize concurrent cancel requests.

---

## Bug 18: Access Token Lifetime Wrong
- **File:** `app/auth.py`
- **What and Why:** `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60)` — with `ACCESS_TOKEN_EXPIRE_MINUTES = 15`, this produced a 900-minute (15-hour) lifetime. Rule #8 requires `exp − iat = exactly 900 seconds`.
- **Fix:** Changed to `timedelta(seconds=900)`.

---

## Bug 19: Refresh Token Not Single-Use
- **File:** `app/auth.py` and `app/routers/auth.py`
- **What and Why:** `POST /auth/refresh` issued new tokens but never invalidated the presented refresh token. The same refresh token could be reused indefinitely, violating rule #8 which requires single-use refresh tokens (reuse → 401).
- **Fix:** Added `_used_refresh_tokens: set[str]` and `consume_refresh_token()` in `app/auth.py` that raises `401` if the JTI was already used. Called in the refresh endpoint before issuing new tokens.

---

## Bug 20: Room Stats In-Memory Not DB-Backed
- **File:** `app/services/stats.py`
- **What and Why:** Stats were tracked in a plain in-memory dict that reset to zero on every process restart, diverging from actual DB state. Rule #14 requires stats to always equal values derivable from the bookings themselves.
- **Fix:** Replaced with a live DB query (`func.count` + `func.sum`) so stats are always derived directly from confirmed bookings in the database.

---

## Bug 21: Export Multi-Tenancy Hole
- **File:** `app/services/export.py`
- **What and Why:** When `include_all=True` and a `room_id` was provided, `fetch_bookings_raw` was called with only `room_id` and no `org_id` filter. An admin could pass a `room_id` from another org and receive that org's booking data, violating rule #9.
- **Fix:** Removed the `fetch_bookings_raw` code path. All cases now go through `_fetch_scoped` which always filters by `org_id`.

---

## Bug 22: Report Cache Not Invalidated on Booking Creation
- **File:** `app/routers/bookings.py`
- **What and Why:** After creating a booking, `cache.invalidate_availability` was called but `cache.invalidate_report` was not. A cached usage report would not reflect the new booking, violating rule #12 which requires the report to reflect current state immediately.
- **Fix:** Added `cache.invalidate_report(user.org_id)` after booking creation.

---

## Bug 23: GET /bookings Returns All Org Bookings for Admins
- **File:** `app/routers/bookings.py`
- **What and Why:** The list query skipped the `Booking.user_id == user.id` filter for admins, returning all bookings in the org. Rule #11 states items are "the caller's own bookings" — this applies to all users including admins. The `GET /bookings` list endpoint is scoped to the caller's own bookings regardless of role.
- **Fix:** Applied `Booking.user_id == user.id` filter unconditionally for all users.
