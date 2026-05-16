# UI Security Assessment

This app is currently a static, browser-only Druglist workspace. It can store local profiles, favorites, drafts, quick access items, rule drafts, and inventory overrides in `localStorage`, but it cannot provide real private multi-user authentication without a backend identity service.

## What This Patch Supports

- Local clinic user registration/edit/remove for browser-scoped preferences.
- Local sign-in style user switching for favorites, quick access, and draft workflow context.
- Live export of local UI state from Admin.
- Clear in-app wording that local profiles are not server-grade authentication.

## Current Security Limits

- No server-side identity, password reset, session revocation, audit trail, or role-based enforcement exists in the static app.
- Local browser storage can be read or cleared by anyone with access to the same browser profile.
- Clinical data edits in Rules/Admin are local drafts unless exported or promoted by a separate repo workflow.
- GitHub Pages/static hosting cannot safely protect patient-specific or private account data by itself.

## Recommended Production Security Next Step

Use a backend identity provider before storing private clinical user data across devices. A practical next PR would add Supabase Auth or another identity backend with:

- server-side user accounts and password reset,
- role-based access for admin/rules/release actions,
- audit logs for every clinical rule edit,
- encrypted server storage for user-specific preferences,
- explicit separation between public drug reference data and private clinical workspace data.
