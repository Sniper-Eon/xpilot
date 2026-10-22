"""Store page (mici), opened from the Plugins page: lists the plugin repository index (store.py), installs, updates
and removes downloaded plugins while offroad. Network and disk work run in a background thread; row values show
the state. Changes apply after a restart. Downloaded plugins are reviewed but not signed."""
import threading

from openpilot.selfdrive.ui.mici.widgets.button import BigButton
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.widgets.scroller import NavScroller
from openpilot.tesla import store


class StorePage(NavScroller):
  def __init__(self):
    super().__init__()
    self._busy = False
    self._status = 'tap Refresh'
    self._entries: list[store.IndexEntry] = []
    self._rows: dict[str, BigButton] = {}
    self._dirty = False
    self._installed: dict[str, str] = store.installed_versions()
    back = BigButton('Back')
    back.set_click_callback(gui_app.pop_widget)
    self._scroller.add_widget(back)
    self.refresh = BigButton('Refresh', description='Download the plugin list from github.com/onemiless/xpilot-plugins.')
    self.refresh.set_click_callback(lambda: self._run(self._fetch))
    self.refresh.set_enabled(lambda: not self._busy)
    self._scroller.add_widget(self.refresh)

  def _run(self, job) -> None:
    if self._busy:
      return
    self._busy = True
    threading.Thread(target=self._job, args=(job,), daemon=True).start()

  def _job(self, job) -> None:
    try:
      job()
    except Exception as e:
      self._status = f'error: {e}'[:60]
    finally:
      self._installed = store.installed_versions()
      self._busy = False

  def _fetch(self) -> None:
    self._status = 'loading...'
    entries, error = store.fetch_index()
    self._entries, self._status, self._dirty = entries, error or f'{len(entries)} plugins', True

  def _current(self, pid: str) -> store.IndexEntry | None:
    """The entry from the latest fetch (rows outlive refreshes; a dropped entry gives None)."""
    return next((e for e in self._entries if e.id == pid), None)

  def _act(self, entry: store.IndexEntry | None) -> None:
    if entry is None:
      return
    if not ui_state.is_offroad():
      self._status = 'park first'
      return
    have = self._installed.get(entry.id)
    if have is not None and (have == entry.version or not entry.installable):
      store.uninstall(entry.id)
      self._status = f'removed {entry.id}: restart to apply'
    else:
      self._status = f'installing {entry.id}...'
      error = store.install(entry)
      self._status = f'{entry.id}: {error}'[:60] if error else f'installed {entry.id}: restart to apply'

  def _row_value(self, entry: store.IndexEntry, installed: dict[str, str]) -> str:
    have = installed.get(entry.id)
    if not entry.installable:
      return f'needs api {entry.api}' if have is None else f'v{have} - tap to remove'
    if have == entry.version:
      return f'v{have} - tap to remove'
    return f'update v{have} -> v{entry.version}' if have else f'v{entry.version} - tap to install'

  def _update_state(self):
    super()._update_state()
    self.refresh.set_value('working...' if self._busy else self._status)
    if self._dirty:  # rebuild rows on the UI thread after a fetch
      self._dirty = False
      for entry in self._entries:
        if entry.id not in self._rows:
          row = BigButton(entry.name, description=f'{entry.description}\n\n{entry.author} - {entry.category} - {entry.id}')
          row.set_click_callback(lambda pid=entry.id: self._run(lambda: self._act(self._current(pid))))
          row.set_enabled(lambda pid=entry.id: not self._busy and ui_state.is_offroad() and
                          (pid in self._installed or getattr(self._current(pid), 'installable', False)))
          self._scroller.add_widget(row)
          self._rows[entry.id] = row
    if not self._busy:
      for entry in self._entries:
        if entry.id in self._rows:
          self._rows[entry.id].set_value(self._row_value(entry, self._installed))
