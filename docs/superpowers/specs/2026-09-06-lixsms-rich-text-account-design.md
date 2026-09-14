# Lixsms Rich-Text Account Parsing Design

## Scope

Extend `utm-notion` account parsing for the exact Feishu rich-text shape used by
the Lixsms source. The change must not alter VM selection, Notion routing, or
the behavior of existing account formats.

## Accepted Shape

The rich-text cell contains, in order:

1. One unlinked, contiguous 10-digit phone number.
2. One displayed HTTPS link whose host is exactly `lixsms.com` and whose link
   target is the SMS platform URL.
3. One or more following linked display fragments which concatenate to exactly
   one email followed immediately by one initial password.

The leading 10 digits are always the phone number. Link targets attached to the
email/password display fragments are not sources of phone or credential data.

## Parsing

Add a provider-specific parser before the current flattened-text branches. It
will preserve list-item boundaries, HTML-unescape the unlinked phone fragment,
validate the first link target as HTTPS on `lixsms.com`, and concatenate only
the display text after that first link.

Split the credential tail at one supported email suffix. The email must be
unique and syntactically valid. The remaining password must be non-empty and
contain both letters and digits. Normalize the 10-digit phone through the
existing phone normalizer.

If any boundary is missing or ambiguous, reject the cell. Do not fall back to
guessing from the link query or from later link targets.

## Safety And Compatibility

- Keep all existing parser branches unchanged.
- Match only this exact rich-text list shape and exact provider host.
- Never log or persist source account values outside the existing verified
  Notion write path.
- Use synthetic fixtures only in tests.

## Verification

Add a regression test using four synthetic rich-text fragments matching the
reported structure. Assert the extracted phone, SMS URL, email, and password.
Add rejection coverage for a non-10-digit prefix and an ambiguous credential
tail. Run the focused `utm-notion` tests, then the full related test module.
After tests pass, retry the public `utm-notion` entry for the same exact
application and VM and require its canonical `status=verified` result.
