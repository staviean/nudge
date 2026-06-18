# 🔧 Dev Workflow

How changes get from the repo to the running Home Assistant, and how to refresh.
See also [[BUILD_PLAN]] and [[Decision-Log]].

## Deploy

The repo lives at `S:\WhereIsMyMind\Nudge`. HA runs at `10.0.0.147` and its `config` folder is
reachable over the Samba share. **`deploy-to-ha.bat`** robocopy-mirrors
`custom_components\nudge` into HA's `config\custom_components\nudge` (gitignored; hardcodes the IP).

## Two refresh modes (important)

- **Python / `manifest.json` behavior change** → deploy, then **restart Home Assistant**
  (Settings → System → Restart). A config-entry reload won't pick up new manifest deps or
  `async_setup`.
- **Frontend JS change (`nudge-card.js`)** → deploy, then in the browser **right-click the reload
  button → "Empty Cache and Hard Reload."**

## Why "Empty Cache and Hard Reload" for JS

HA's frontend runs a **service worker** that aggressively caches resources. A plain Ctrl+Shift+R
reloads the page but can still serve the *old cached* card. "Empty Cache and Hard Reload"
(available when DevTools is open) bypasses the service worker. If it's still stale:
DevTools → **Application → Service Workers → Unregister**, then reload.

## Verifying the new code actually loaded

The card logs a version tag to the browser console, e.g. `NUDGE-CARD 6b create + categories`.
Bump that string on each card change so you can confirm in the Console that the latest code is live.

## Sanity-checking before deploy

- Python recurrence logic: pure-Python unit tests run in the dev sandbox (no HA needed).
- Card JS: `node --check` for syntax before deploying.
