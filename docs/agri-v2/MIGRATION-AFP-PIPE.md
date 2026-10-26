# AFP pipe migration and key connection

- Destination: `kapitansaman/afp-pipe`; production branch: `feat/agri-generator-v2-2905-merge593`.
- Old agriculture schedule was removed and old production/research flags were paused. Original queues, attempts and receipts are preserved.
- GitHub Secrets `AGNES_API_KEY_1` through `AGNES_API_KEY_22` map explicitly to internal slots `AGNES_API_KEY`, `AGNES_API_KEY2` … `AGNES_API_KEY22` in each agriculture workflow.
- Secret values and credential fingerprints are never written to Git or logs. New key capability evidence is bound to this repository and credential set `afp-pipe-22-keys-v1`; historical evidence is not authorization for new credentials.
- The fresh connection workflow makes at most one tiny text probe and one image probe per unique configured key. Any shared rate/quota/capacity/uncertain response stops the audit; keys do not bypass provider limits. Results distinguish configured, unique, tested and verified capabilities.
- Production remains paused pending fresh capability evidence and the three WordPress Secrets: `AFP_WP_BASE_URL`, `AFP_WP_USERNAME`, `AFP_WP_APP_PASSWORD`. Credentials must be set through GitHub Secrets, not committed.
- Historical one-off recovery and pilot requests are disabled in the new normal scheduler. Existing articles, accepted images and retry counters must not be regenerated or reset.
- Image admission, telemetry and workflow guards now point to the destination. Legacy blog workflows remain disabled; only selected agriculture workflows may be activated.
- Content requirements remain unchanged: two shared images, Persian plus Russian/Arabic/Tajik/English, same-language internal links, source validation and critical image checks.

- Active image model changed by owner request to `agnes-image-2.5-flash`. Model-specific capability evidence for 2.1 is not approval for 2.5; production remains paused. Historical audit requests and output records remain unchanged.

- Owner expanded the current set to 30 slots (`AGNES_API_KEY_1` … `_30`), bound as `afp-pipe-30-keys-v1`. Prior 22-key reports remain historical. The live setup run checks text/uniqueness for all 30 and sends at most ONE image request for model 2.5, after any provider cooldown, with no publication. Only individually verified image keys can enter production rotation.

- Image generation now has an owner-authorized lifetime round of at most 30 unique credentials per exact model/prompt/reference/cohort. Invalid authentication, image scope or malformed image output advances to the next unique candidate. A valid image stops the round and is cached with its digest. Shared quota/rate/queue responses and uncertain timeouts defer the next candidate until the provider deadline; critical visual QA never regenerates automatically. Existing article/recovery budgets remain additional safety limits. No counters or historical artifacts are reset.
