# Navigation signal and GPIO prompt admission

Consulted upstream onemiless/xpilot 372a943df6b714bb1596894cb62bba8de0e74bf4
and xpilot-plugins 1c9b8f134863e3e19571f7f1633c32bf2119d1b9 developer rules,
hard rules, lane-change/alert contracts and manifest capabilities. New upstream
hooks do not imply availability on the active old device host (ceb0163 + overlays).

Generic buzzer_policy / sound claim lets enabled plugins narrow ordinary GPIO
prompts. Backend applies it to prompt/promptRepeat only; emergency warnings and
MADS on/off remain native. Invalid/faulting policy is removed, preserving native
sound behavior. A new advertised capability rejects incompatible old hosts.
No CAN rule, firmware, planner-control or steering-rate limit is changed.

Before implementation, buzzer_check failed because the old backend lacked
ordinary-prompt admission. Paired navigation checks reproduced missing-lane lamp
suppression, chimes despite denied/opposite starts, missing physical feedback,
and missing exit/ramp relative preparation. Validation results are recorded in
the workspace evening-navigation-audit-20261028/REPAIR.md. No device activation
or road validation is implied by source tests.

## Device compatibility deployment

User explicitly authorized deployment. The active older device host was retained;
no wholesale runtime-rule/ABI-1 migration was performed. Published behavior from
host 71e1622 and store a9f7a6d was applied as a bounded legacy-host compatibility
overlay: generic buzzer hook/collector and its sound-claim admission, GPIO prompt
routing, and the navigation intent/planning/policy/chime modules. The installed
legacy package reports 1.5.10; it is not the ABI-1 store package 2.0.1. Legacy
setup/safety manifests and the physical-lamp controller were retained.

The actual old-host discovery, enabled/disabled master and 62 relevant regression
cases passed locally against the assembled overlay before installation. Live
fresh device/panda offroad and ignition/control-off guards passed before writes
and reboot. Exact preimage checks, atomic file replacements and a recoverable
backup cover 10 files under /data/nav-buzzer-repair-20261028. Device firmware and
protected DS engagement source hashes, plus selected navigation settings, stayed
unchanged. Raw settings and logs are private, outside this repository.

After reboot, matching file hashes, empty plugin load errors/fault record, running
navigation/UI/selfdrive/buzzer processes and fresh model/vehicle/control messages
were verified. Gear P, speed zero, lateral/longitudinal inactive at the later
read-only check. The vehicle powered on after the guarded reboot; no subsequent
writes or control requests were made. Historical interruptRateCan2 recurred
onroad and remains an independent diagnostic item; it was not hidden or bypassed.
Physical chime timing and actual lane-change road performance remain unvalidated.
No visual-model weights were changed by this deployment.
