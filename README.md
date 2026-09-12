# GlassBlock

A minimal, self-built Chrome ad blocker based on the Manifest V3 `declarativeNetRequest` API, with full **EasyList**, **EasyList China** and **EasyPrivacy** coverage converted to native Chrome rule format. The name says the pitch: like a pane of glass, everything about it is transparent — you can see (and audit) exactly what it does.

The extension code is a few hundred lines with zero dependencies, and filtering is declarative — the browser engine does the matching, not a content script reading your pages. You can audit every line, and nobody can push a malicious update to you.

It holds three permissions, and it is worth knowing exactly what each buys:

| Permission | Why | Scope |
|---|---|---|
| `declarativeNetRequest` | The blocking itself | No page access; rules are evaluated by Chrome |
| `activeTab` | Reading the current tab's hostname, so "Pause on this site" knows which site you mean | Granted only for the tab you are on, only when you click the toolbar icon, and it lapses on navigation |
| `declarativeNetRequestFeedback` | The match counter in the popup | Chrome grants it to unpacked extensions only. Drop it from `manifest.json` if you ever pack this — the popup degrades quietly |

If you would rather not grant `activeTab`, delete it from `manifest.json` and delete the `.site` block from `popup.html`; everything else keeps working.

## File structure

| File | Purpose |
|------|---------|
| `manifest.json` | Extension manifest (permissions, rulesets, content script, popup) |
| `rules_easylist.json` | EasyList converted to declarativeNetRequest rules (ads) |
| `rules_easylistchina.json` | EasyList China converted to declarativeNetRequest rules (mainland ad networks) |
| `rules_easyprivacy.json` | EasyPrivacy converted to declarativeNetRequest rules (trackers) |
| `rules_custom.json` | Your own hand-written rules |
| `hide-generic.css` | **Generated.** EasyList/EasyList China generic element-hiding rules as plain CSS (~14k selectors) |
| `hide-ads.css` | Hand-written cosmetic filtering, applied to every site |
| `hide-huangguo.css` | Site-scoped cosmetic rules for huangguoai.com / huangguoac.com, whose ads are first-party and unblockable at network level |
| `popup.html` / `popup.js` | Toolbar popup with per-ruleset on/off toggles |
| `tools/convert.py` | Converter: Adblock Plus filter syntax → MV3 rule JSON |
| `tools/gen-cosmetic.py` | Generator: generic `##` element-hiding filters → `hide-generic.css` |
| `tools/update-lists.sh` | One-command refresh of the EasyList/EasyPrivacy rule files |
| `CHANGELOG.md` | Version history and release notes |
| `icons/` | Master `icon.svg` plus exported `icon16/48/128.png` used by the manifest |

## Installation

This is an unpacked extension for personal use — no Chrome Web Store required:

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** (top-left)
4. Select this folder (`glassblock/`)
5. Done. The icon appears in the toolbar (it may be tucked into the puzzle-piece menu — pin it if you like)

> **Note:** An unpacked extension is bound to its folder path. Do not move or delete this folder, or the extension will stop working. Chrome may occasionally remind you about developer-mode extensions on startup — click "Keep" to dismiss.

### Verifying it works

Open any ad-heavy news site, press F12 → **Network** tab, and reload. Requests to domains like `doubleclick.net` or `googlesyndication.com` should show up in red as `(blocked:other)`.

## Daily use

- **Toggle rulesets**: click the toolbar icon. Each ruleset (Custom / EasyList / EasyList China / EasyPrivacy) can be enabled or disabled independently and takes effect immediately. The cosmetic CSS is not affected by these toggles.
- **A site broke?** Pause the rulesets via the popup and reload to confirm the blocker is the cause. If it is, see "Whitelisting a site" below.

## Configuration

After editing any file, go back to `chrome://extensions` and click the **reload (↻) icon** on the extension card. Then reload any open tabs.

### Updating the filter lists

The bundled EasyList/EasyPrivacy snapshots are current as of the commit date. Upstream, both lists change daily (new ad domains, false-positive fixes), so refresh them every week or two:

```bash
tools/update-lists.sh
```

The script downloads the latest lists, converts them, verifies the total stays under Chrome's guaranteed 30,000-rule limit, and only then replaces the rule files — a failed download can never leave you with corrupt rules. Afterwards, reload the extension at `chrome://extensions` (Chrome only reads static rule files at load time, so this last click cannot be automated).

To run it automatically, add a cron entry (`crontab -e`):

```cron
# Refresh filter lists every Monday at 09:00 (use the absolute path to this repo)
0 9 * * 1 /path/to/my-adblocker/tools/update-lists.sh >> /tmp/adblock-update.log 2>&1
```

You'll still need to click reload in Chrome once after each refresh.

Under the hood, `tools/convert.py` handles the standard network-filter syntax (`||domain^`, `$third-party`, `$script`, `$domain=`, `@@` exceptions, ...) and skips what declarativeNetRequest cannot express (cosmetic rules, regex filters, `$csp`, `$redirect`, `$removeparam`, `$popup`); it prints a summary of what was converted and skipped.

### Adding your own blocking rules

Edit `rules_custom.json`. To block another ad domain (subdomains included), add it to the `requestDomains` array of rule 1:

```json
"requestDomains": [
  "doubleclick.net",
  "new-ad-domain.com"
]
```

To add a different kind of rule, append a new object with a unique `id`:

```json
{
  "id": 3,
  "priority": 1,
  "action": { "type": "block" },
  "condition": {
    "urlFilter": "/ads/banner/",
    "resourceTypes": ["image", "script"]
  }
}
```

Common `urlFilter` syntax:
- `||example.com^` — all requests to the domain and its subdomains
- `/ads/` — URL path contains `/ads/`
- `*` — wildcard

Full reference: [Chrome declarativeNetRequest documentation](https://developer.chrome.com/docs/extensions/reference/api/declarativeNetRequest).

### Whitelisting a site

The quick way: open the popup and click **Pause on this site**. That writes a
dynamic `allowAllRequests` rule for the current hostname (and its subdomains) at
priority 100, above every static rule, and reloads the tab. Click **Resume on
this site** to remove it. Dynamic rules survive browser restarts and are not
touched by `tools/update-lists.sh`.

For a permanent entry you want under version control, add an `allow` rule to
`rules_custom.json` with a higher `priority` than the block rules:

```json
{
  "id": 100,
  "priority": 10,
  "action": { "type": "allow" },
  "condition": {
    "initiatorDomains": ["site-to-whitelist.com"]
  }
}
```

### Hiding more ad elements

Edit `hide-ads.css` — **not** `hide-generic.css`, which is regenerated from
upstream on every `tools/update-lists.sh` run and will lose your edits. To find a selector: right-click the ad → **Inspect**, find the ad container's `id` or `class`, and add it:

```css
.some-ad-class,
#some-ad-id {
  display: none !important;
}
```

> Beware of overly broad selectors (e.g. `.ad` will also hide legitimate elements that happen to use that class name).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Rule changes don't take effect | Click reload (↻) on `chrome://extensions`, then reload the page |
| Extension card shows a red "Errors" badge | Open it — usually a JSON syntax error in a rules file (trailing comma, duplicate `id`) |
| A site's layout broke | Pause via the popup to confirm; add an `allow` rule if it's network blocking, or remove the CSS selector if it's cosmetic |
| Ads still showing | F12 → Network, find the ad request's domain, add it to `rules_custom.json` |
| Ruleset fails to enable | Chrome guarantees 30,000 static rules and this extension ships ~19,600, so it fits; if you add more lists, watch the total. `tools/update-lists.sh` refuses to install a set that would exceed the limit |

## Limitations (by design)

- Cosmetic filtering is partial. The ~14,200 *generic* element-hiding rules from EasyList/EasyList China ship in `hide-generic.css`, but the ~15,900 *domain-scoped* ones (`example.com##.promo`) do not — a global stylesheet cannot scope by site, so those need a per-site file like `hide-huangguo.css`. uBlock's procedural filters (`:has-text()`, `:upward()`) need a DOM engine and are out of scope entirely.
- `#@#` un-hide exceptions cannot be expressed in a global stylesheet, so any selector carrying one is dropped rather than applied — erring toward showing an ad over breaking a page.
- Cannot block YouTube in-video ads or first-party ads (served from the same domain as the content).
- No anti-adblock countermeasures — some sites will detect blocking and complain.
- Regex filters and `$csp`/`$redirect`/`$removeparam` filters from EasyList are skipped (declarativeNetRequest cannot express them; they are a small fraction of the list).

## Licensing and attribution

- Extension code (`manifest.json`, `popup.*`, `hide-ads.css`, `hide-huangguo.css`, `tools/convert.py`, `tools/gen-cosmetic.py`): MIT.
- `rules_easylist.json`, `rules_easylistchina.json`, `rules_easyprivacy.json` and **`hide-generic.css`** are derived from [EasyList, EasyList China and EasyPrivacy](https://easylist.to/), © The EasyList authors, dual-licensed under [GPLv3](https://www.gnu.org/licenses/gpl-3.0.html) and [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). These files remain under those licenses.
