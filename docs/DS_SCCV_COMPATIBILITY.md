# Retained DS SCCV fixes

The workspace owner requires preserving the DS repairs from the former branch. This restores the two existing SCCV fixes from the 2026-10-23 reference checkout, rather than introducing a new vehicle feature or planner role. The shared SP SCCV class uses commanded `controlsState.desiredCurvature` for turn-phase lateral acceleration, and requires five consecutive qualifying model frames before entering. Both SP and TN import this shared implementation; keeping one implementation avoids different curve phases in their two controllers.

The native SmartCruiseControlVision switch and its existing cruise-settings plugin mapping remain in control. Disabled/override/low-speed/gap paths clear confirmation. The predicted p97 threshold, lateral-acceleration regulator, minimum speed, acceleration limits, MPC, FCW, driver overrides, navigation master and firmware are unchanged.

Failure checks are in `tools/sp_tesla_e2e/sccv_compat_check.py`: the prior source fails commanded-curvature, continuity and turn-phase cases; the retained source passes six cases plus four continuity subcases. Nine reference SCCV tests pass, including the minimized straight-road transient fixture. The fixture contains numerical regression inputs only, without coordinates or route identity.

This does not prove every road bend will slow sufficiently. Three locally retained full logs provide 3,618 model frames but no active entering/turning episode in this replay, so they establish replay compatibility only. Sparse qlogs without modelV2 cannot validate model-frame confirmation timing. Test source, local checks, installation, process activation and actual road results must be reported separately.
