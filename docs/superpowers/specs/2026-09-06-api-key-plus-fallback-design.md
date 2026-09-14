# API Key Plus Fallback Design

## Goal

Allow the integrations automation to create an API key when Apple does not render a `Generate API Key` button and instead exposes the add control beside the `Active (1)` heading.

## Behavior

Keep the existing `Generate API Key` path as the first choice. If that button is not visible, locate exactly one heading matching `Active (number)`, move to its parent control row, and require exactly one accessible button there. Click that button and continue through the existing name, role, generation, issuer, key ID, and P8 download steps. Any missing or ambiguous target remains a hard failure.

## Scope

The current source lives in the bound guest at `/Users/zwfo/Downloads/Fire_One_en1.3/src/fill-description.ts`; the host repository only runs the public `utm-script` entry. The change is therefore applied to the guest source and verified through the public entry, with no coordinate-based interaction and no browser-session reset.

## Verification

First verify the old source does not contain the fallback. After the change, verify the source contains the semantic `Active (number)` heading fallback and run the public `utm-script` entry on the same application, VM, IP, user, and Edge/CDP session. Do not continue to `utm-image` unless `UTM_18=verified` is emitted.
