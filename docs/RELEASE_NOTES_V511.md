# Web Search Plus 5.1.1

Fixes from the 5.1 reviews: provider keys stay in the active Hermes profile, refused URLs stay out of keyless rescue, and extraction and deadlines behave as documented. No configuration changes are needed.

## Security

- **Refused URLs stay local.** The native `wsp` backend marks URLs it refused on purpose (private or internal addresses, `file:` and other non-HTTP schemes, URLs without a host) with Hermes' `blocked_by_policy`, so Hermes' keyless rescue does not send them to third-party services. `hermes web-search-plus status` shows whether `web.keyless_rescue` is on and how to turn it off.
- **Keys only from the profile.** Under Hermes, `api_key` in `config.json` is ignored with a warning, and `status` names the affected provider. DonSeTch no longer runs a `config.json` `api_key` as its binary path.
- **No secrets in output.** `status --json`, `config show --json` and dry-runs show secret fields only as `set` or `not set`. SearXNG URLs show without user, password and query, also in state files and error messages.
- **Cache per credential.** On a multi-profile gateway a profile no longer gets cached results from a key or SearXNG instance it does not have.

## Fixed

- **Deadlines hold.** No provider request starts after the request deadline. Batch extraction keeps the pages it already fetched and marks the rest `not tried`. A deadline stop no longer opens the provider's circuit or uses budget.
- **One result per URL.** Extract returns exactly one result per requested URL, in request order. `?ref=1` and `?ref=2` stay separate, and content returned under a redirected URL is kept instead of paying a second provider.
- **The serving provider is named.** When a fallback provider serves the pages, the header, routing, receipt and cache name that provider.
- **Brave 429** falls back to the next provider when one is left, instead of waiting.
- **Budgets fail closed** when the SQLite state store is unavailable.
- **`hermes plugins validate`** no longer warns about a private import.

## Changed

- Provider SDK: `RequestDeadlineExceeded`, `deadline_passed()`, `dispatch_timeout()` and `remaining_seconds()` are public, for providers with their own transport. See `docs/PROVIDER_SDK.md`.
- `status --json` adds `ignored_file_keys` and `hermes_native`.

Full list: [CHANGELOG](../CHANGELOG.md).
