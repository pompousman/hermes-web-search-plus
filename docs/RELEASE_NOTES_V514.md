# Web Search Plus 5.1.4

The DonSeTch provider works with current DonSeTch releases again. No configuration changes are needed.

## Fixed

- **DonSeTch 4.7.1 and newer.** Since 4.7.1, DonSeTch folds results for MCP clients it does not recognize into the text content (a leading `[meta] {json}` line) and drops `structuredContent`, which Web Search Plus reads. Every DonSeTch search failed with `donsetch_search_contract_failed`. Web Search Plus now starts DonSeTch with `DONSETCH_MCP__TEXT_ONLY=false`, upstream's documented opt-in for the split result. If a folded result arrives anyway, it reads the leading `[meta]` block. The tested version is now 4.10.1; 4.7.0 and newer work.
- **Tests:** a leftover pre-5.1 `.env` next to the checkout (for example in a live install) no longer makes unrelated tests fail.

## Thanks

Huge thanks to [@friday-cp](https://github.com/friday-cp) for [#164](https://github.com/robbyczgw-cla/hermes-web-search-plus/issues/164). The report came with the root cause, the upstream changelog, the exact opt-in, a reproduction across versions and the upstream cross-reference. This release implements that fix.

Full list: [CHANGELOG](../CHANGELOG.md).
