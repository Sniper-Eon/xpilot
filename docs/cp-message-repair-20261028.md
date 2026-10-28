# Onroad CP message conflict repair

The installed CP receiver worked while parked, but the card hook opened a second
cereal pluginMsg publisher when vehicle processes started. A real device crash
record shows MultiplePublishersError in cp_navd, followed by selfdrived's
process_not_running event naming cp_navd. This is a failed receiver, not evidence
that the user forgot to enable the plugin: they subsequently selected TesNav.

Selectively backport onemiless/xpilot 38b158fbcc9a3cfad0b12b44d008bb9a32839dae:
plugin_msgd.py, its send/read API, manager registration and dead-Python-process
restart. The broker is the sole cereal publisher; authenticated local senders
have source/claim, TTL, rate and byte checks. No vehicle enable/disable condition,
required-process check, firmware policy or cereal schema is bypassed or migrated.
The protected DS/device overlays must be retained during installation.

Failure checks were added before the implementation. The native host test failed
on the missing broker; the CP card regression failed when observe_can attempted
to create another PubMaster. Both pass after repair. The paired cp_nav 0.1.1 and
navassist 1.5.9 producers must be installed with this host before restarting;
leaving any old direct pluginMsg publisher active is incompatible. Entry imports
reject older hosts without the broker. Retain each plugin's own master switch.

Local validation: generated files, risk classifier, all workflow host checks,
store_e2e, fork_pair_check and native message E2E: exit 0. The latter used actual
Darwin IPC and four concurrent producer processes, delivery of 81 samples,
expiry, spoofed source rejection, bounded rate, broker absence/restart and private
directory checks. Params used an isolated fixture because the local native
library predates plugin keys. Linux SCM credential authenticity and large-payload
fairness require the separate Linux CI result; Darwin explicitly reports those
limits as unexercised. The imported E2E uses ordinary JSON fixtures instead of
upstream renamed cereal types, preserving the device's existing schema.

Source/local verification is separate from activation: no repair has yet been
installed on the driving device, no phone ADB session is available, and real
phone connection plus stationary onroad-start validation remain required. Do not
claim an APK handshake or road behavior was verified by the loopback tests.
