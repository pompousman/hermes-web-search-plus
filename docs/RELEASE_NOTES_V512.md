# Web Search Plus 5.1.2

Extraction keeps what it already fetched when a provider stops mid-batch, every requested URL gets an answer, and the search text is safer to read and easier to parse. No configuration changes are needed.

## Fixed

- **Pages survive a mid-batch rate limit.** When a provider hits a rate limit, runs out of credits or rejects the key partway through a batch (seen with Firecrawl's free plan), WSP keeps the pages it already fetched. The remaining URLs get `not tried: provider rate limit reached` (or the matching cause) and go to the next provider. The circuit records the failure, so automatic routing backs off.
- **Every URL gets an answer.** URLs past the per-call limit (default 10) get their own `not tried: limit of 10 URLs per call reached` row instead of disappearing, in the tool, RPC and native output.
- **Snippets stay inside their result.** Every line of a multi-line snippet is indented like the URL line, so page text such as `2. Install the build` can no longer look like the next result, or let a page fake one. A golden test freezes the search and extract text layout.
- **`status` explains ignored settings.** Under Hermes, `allow_public` flags and a SearXNG URL in `config.json` are ignored on purpose. `status` and `status --json` (`ignored_file_settings`) now say so and name the profile setting to use instead. The URL is never printed.

## Added

- **Machine-readable header bits.** The search header ends with `results=N`, `elapsed_ms=N` and, after a fallback, `fallback_from=a,b`. Research adds `providers=` and `pages=`. A cache hit repeats how the cached search was routed. Existing bits keep their wording and order; JSON, RPC and native output are unchanged. The user guide describes the header.

```text
[Provider: brave | auto-routed | medium confidence | no_signals_matched | results=5 | elapsed_ms=1708]
[Provider: brave | cached 12s ago | auto-routed | medium confidence | no_signals_matched | results=5 | elapsed_ms=138]
[Provider: research | auto-routed | medium confidence | intent_general | providers=brave,tavily | pages=3 | results=5 | elapsed_ms=5571]
```

Full list: [CHANGELOG](../CHANGELOG.md).
