# Navigation lamps: ABI2 table rejected before upload

The 2026-10-29 drive used navassist 2.3.0 with a template_clone.v2 rule. The host and running DEV-c1f33cf2-DEBUG Panda advertise ABI2, but PandaSafety::loadRules checked that the uploaded table's ABI was exactly 1. It consequently cleared the feature rule table and continued with native Tesla control, explaining why navigation could request lamps while Panda rejected the 0x3E9 frames. A later drive selected nav_lane_change instead of navassist; it recorded no navassist plugin messages or 0x3E9 output. Those are distinct failures; the latter selection was corrected through the existing mutually exclusive switch.

The fix accepts table ABI1 and ABI2 after the existing exact CAPS check. All size, CRC, byte, template, counter, timing, engagement and brake checks remain unchanged. Unsupported table ABI3 is CRC-valid in the regression fixture and must be rejected before EP2 writes. No firmware or Tesla safety-mode change is needed.

The old native upload harness used only ABI1 fixtures, even after ABI2 support was introduced. Its host-manifest fixture now exercises a real v2 rule; the unchanged ABI1 reference still covers backward compatibility. Before the fix, PANDA_RULES_CASE=host failed because XpilotPandaRulesFault latched and no table uploaded. After the fix, the full native loader and SPI checks passed, including ABI1, ABI2, unsupported version, revocation, timeout and reset cases.

Raw driving data stays in the private workspace. Three recorded request/cancel frames pass the current firmware harness when their real templates and recorded authority are supplied. Full segment replay does not reconstruct the recorded lateral authority from a mid-drive starting point, so it is not evidence of actual vehicle lamp execution. Road validation remains outstanding.

Source: this scoped host commit. Local build/native validation and actual device installation are recorded separately in the deployment report. Host and firmware source/readback baselines are retained privately; firmware version and signature were read without Panda initialization or control writes.
