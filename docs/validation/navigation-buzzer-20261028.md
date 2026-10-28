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
