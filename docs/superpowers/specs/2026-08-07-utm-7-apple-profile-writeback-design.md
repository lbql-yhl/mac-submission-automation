# UTM-7 Apple Profile Writeback Design

## Scope

After `utm-7` has proved that the expected Apple Account is signed in, the same
entry must read the account holder name and birthday from the already-open
macOS System Settings Apple Account pages and write both values to the matching
Notion registration page. This change does not alter `utm-8` or any skill from
`utm-21` through `utm-25`, and it does not enable or change the Feishu start
entry.

## Canonical Notion fields

The canonical account-section labels are:

- `用户名：`
- `生日（格式年/月/日）：`

`utm-notion` must retain `生日（格式年/月/日）：` exactly for newly copied and
existing registration pages. There is no label migration and no second birthday
alias. Zero or duplicate occurrences of this exact label are conflicts and must
block.

System Settings displays Birthday in month/day/year order. The guest reader
must parse that display as named `month`, `day`, and `year` components, validate
them as a real calendar date, and return the components rather than an
unlabelled ambiguous date string. The host writes the value to Notion in the
label's declared year/month/day order, normalized to `YYYY/M/D`. For example,
Apple `3/9/1999` becomes Notion `1999/3/9`. The account name retains Apple's
displayed spelling, capitalization, and internal spacing after trimming outer
whitespace.

`utm-business` must read only `生日（格式年/月/日）：`, parse it only as
year/month/day, validate the real date, and construct named year/month/day
values before formatting a downstream agreement field. It must not accept a
month/day/year Notion value or guess a date order from numeric ranges. This
makes the Apple-to-Notion conversion boundary explicit and prevents a later
agreement from swapping month and day.

## Guest Accessibility reader

A focused project helper reads System Settings through PyObjC Accessibility.
It must be included in `utm-7`'s atomic shared-helper synchronization and run
from the canonical guest shared mount through fixed-password SSH. It must not
be copied to guest Downloads, and it must not use screenshots, OCR, coordinates,
Computer Use, Quartz keyboard events, clipboard operations, or guest Terminal.

The reader accepts the expected email through SSH stdin memory and performs
these semantic steps:

1. Reuse the existing System Settings process left open by the verified login
   flow and independently find the expected email exactly once.
2. Read the unique account name associated with the Apple Account header above
   that email.
3. Activate the unique enabled `Personal Information` row.
4. Wait at least three seconds and reread the current Accessibility tree.
5. Read the unique `Birthday` row value, parse it strictly in Apple's
   month/day/year display order, and validate it as a real calendar date.
6. Return only a JSON object containing the name and integer `birth_year`,
   `birth_month`, and `birth_day` values to the host process. No account secret
   or ambiguous date string is printed or persisted in the guest.

Every navigation action is followed by a fresh Accessibility-tree read. A
missing or duplicate email, header name, Personal Information row, Birthday
row, or invalid date blocks the workflow before Notion mutation.

## Host orchestration and Notion transaction

`scripts/utm_7_login.py` remains the only host entry. After the existing login
helper returns all login verification markers, it invokes the profile reader
through the same verified shared mount and password-SSH transport.

Before writing, the host independently rereads both canonical Notion fields.
For each field, an empty value may be filled and an identical value is
idempotent. A different non-empty value is an ownership conflict and blocks;
the entry never silently replaces it. The two-field update is rollback
protected: if the second write or either independent readback fails, restore
the exact before-state and independently verify the rollback. Success requires
exact readback of both values and emits:

```text
APPLE_ACCOUNT_PROFILE=verified
NOTION_USERNAME=verified
NOTION_BIRTHDAY=verified
UTM_7=verified
```

Only then may the continuous workflow hand off the same run, VM, IP, SSH user,
and System Settings session to `utm-8`.

## Failure and recovery boundaries

All recoverable Accessibility and shared-mount failures use the existing
three-round `utm-7` recovery rules against the same exact VM. Notion conflicts,
duplicate semantic targets, or an invalid birthday are read-only-rechecked
three times and then use the existing last fault-card boundary. The workflow
must never ask the user to provide the name or birthday manually.

## Tests

Automated tests must prove:

- exact preservation of `生日（格式年/月/日）：` and rejection of missing or
  duplicate labels;
- exact Accessibility extraction and ambiguity rejection;
- strict Apple `M/D/YYYY` parsing, named date components, Notion `YYYY/M/D`
  formatting, and invalid-date rejection;
- strict downstream year/month/day parsing and correct agreement
  month/day/year formatting without heuristic date-order guessing;
- empty-write, equal-idempotent, conflict-blocking, rollback, and independent
  readback behavior for both Notion fields;
- helper synchronization and SSH-stdin-only transport;
- `UTM_7=verified` is impossible before both writeback markers;
- existing detailed-skill, continuous-handoff, portability, and Notion
  contract tests remain green.
