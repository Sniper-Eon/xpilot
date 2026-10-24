## What changes

<!-- What this changes on the road or on the screen, and why. -->

## Repository

- [ ] This is a system change (host, store, UI, core plugins, panda safety, checks, docs). Plugin changes go to onemiless/xpilot-plugins.

## Verification

- [ ] Host checks (XPILOT.md section 11) pass locally
- [ ] Build / safety tests / MISRA (only if panda safety or compiled code changed): paste commands, results and the machine below. CI does not run these.
- [ ] New safety header is `<plugin id>.h`; every TX allowed without `controls_allowed` is in XPILOT.md section 6
- [ ] Tested on a device (commit on the device: )
- [ ] Companion pull request in onemiless/xpilot-plugins (link, if any): 
