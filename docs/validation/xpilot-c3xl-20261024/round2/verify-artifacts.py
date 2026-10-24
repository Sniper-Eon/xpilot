"""Offline round-2 E2E evidence verification; no device/network access or parameter writes."""
import hashlib,json,struct
from pathlib import Path
R=Path(__file__).resolve().parent
read=lambda name:json.loads((R/'evidence'/name).read_text())
for line in (R/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1)
 assert hashlib.sha256((R/name).read_bytes()).hexdigest()==expected,name
result=json.loads((R/'result.json').read_text())
assert result['status']=='DONE' and result['round']==2
assert result['device_before']=='65bb09e3d5d306487d005f15cef799e31cf37fa2'
assert result['device_after']=='4292551111be2d7afa7cf9aa158841fb712e740b'
assert all(v=='PASS' for v in result['failure_modes'].values())
assert {r['script'] for r in result['checks'] if r['rc']!='0'}=={'big_screen_e2e.py'}
assert read('outcome.json')['big_screen_classification']=='ENV'
assert read('base-big-screen-result.json')['errors']==read('head-big-screen-result.json')['errors']
assert len(result['checks'])==15
assert all(read('outcome.json')[k] for k in 'abcd')
assert read('outcome.json')['same_plugin_params'] and read('outcome.json')['same_store_files']
for name in ('base-big-screen-result.json','head-big-screen-result.json'):
 d=read(name)
 assert not d['passed'] and len(d['cases'])==22
 assert 'line 332, in steps' in str(d['errors']) and 'no data tile to drag' in str(d['errors'])
assert (R/'evidence/base-big-screen-source.sha256').read_text().split()[0]==(R/'evidence/head-big-screen-source.sha256').read_text().split()[0]
assert read('names-base.json')==read('names-head.json')
assert len(read('names-head.json')['names'])==47 and not read('names-head.json')['duplicates']
for name in ('production-first-summary.json','production-final-summary.json'):
 d=read(name)
 assert d['passed'] and d['elapsed_seconds']>=120
 assert d['all_names_match'] and d['all_running_match']
 assert all(len(pids)==1 for pids in d['pid_sets'].values())
replay=read('replay-comparison.json')
assert replay['passed'] and replay['tolerance']==0
assert replay['ignored_fields']==['logMonoTime','carState.cumLagMs','controlsState.deprecated.cumLagMs','controlsState.deprecated.startMonoTime']
assert {p:sum(d['base_counts'].values()) for p,d in replay['processes'].items()}=={'selfdrived':12069,'controlsd':17919,'card':19062}
for proc in replay['processes'].values():
 assert proc['base_counts']==proc['head_counts']
 assert all(d['differing_frames']==0 for d in proc['types'].values())
pandas=[read(n) for n in ('panda-before.json','panda-post-build.json','panda-publish.json')]
assert len({d['signature'] for d in pandas})==1
assert all(d['signature']==d['built_signature'] for d in pandas)
assert all(not d['health']['controls_allowed'] and not d['health']['faults'] and not d['health']['ignition_line'] and not d['health']['ignition_can'] for d in pandas)
assert all(d['total_tx_cnt']==0 for d in pandas[-1]['can_health'])
gate=read('gate-publish.json')
assert gate['head']==result['device_after'] and gate['service']=='active'
assert gate['IsOffroad'] and not gate['IsEngaged'] and not gate['started'] and not gate['faults'] and not gate['load_errors']
identity=read('runtime-identity.json')
assert identity['head']==identity['param_git_commit']==result['device_after']
assert identity['branch']=='xpilot' and not identity['defaults_marker_present']
assert identity['updater_target_branch']=='xpilot'
ui=read('core-ui-result.json')
assert ui['passed'] and not ui['missing_roles'] and not ui['offroad_alerts'] and not ui['load_errors']
assert all(p['toggle_state'] and not p['toggle_enabled'] for p in ui['categories'].values())
for p in (R/'screenshots').glob('*.png'):
 d=p.read_bytes()
 assert len(d)<400000 and struct.unpack('>II',d[16:24])==(2160,1080),p
perf=read('overhead.json')
assert perf['calls_per_variant']==10000 and not perf['problem']
assert perf['p99_difference_us']<200 and perf['extra']['p99_us']<200
preserve=read('preservation-final.json')
assert preserve['all_params_restored_before_start'] and preserve['store_unchanged'] and preserve['dirty_unchanged'] and preserve['defaults_marker_restored']
assert preserve['original_count']==preserve['current_count']==156
assert {Path(p).name for p in preserve['final_deltas']} <= {'BootCount','CurrentBootlog','GitCommit','GitCommitDate','LastUpdateTime','ModelManager_LastSyncTime','UpdateAvailable','UpdaterAvailableBranches','UpdaterCurrentDescription','UpdaterLastFetchTime','UptimeOffroad'}
assert read('activation-recovery.json')['native_unchanged']
q=read('pending-update-quarantine.json')
assert q['active_commit']==result['device_after'] and not q['init_exists'] and not q['consistent_exists']
assert q['future_updater_can_restage']
assert read('source-identity.json')['forbidden_changed_paths']==[]
assert read('plugins-copy-proof.json')['device_equal']
assert read('store-index-single-attempt.json')['attempts']==1 and read('store-index-single-attempt.json')['explicit_retries']==0
print(json.dumps({'round':2,'artifact_verification':'PASS','validation_outcome':'DONE','compared_messages_per_tree':49050,'differences':0,'device_after':result['device_after'],'env':['paired big_screen line 332','network'],'operational_risk':'updater can restage baseline on later checks'},indent=2))
