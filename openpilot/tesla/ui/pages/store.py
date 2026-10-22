"""Store page (native, sub-page of Plugins): Refresh row, then one row per plugin index entry with Install/Update/Remove.
Network and disk work run in one background thread (offroad.StoreJobs); rows are added on the UI thread after a fetch."""
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.widgets.list_view import ButtonAction, ListItem
from openpilot.tesla.ui.offroad import StoreJobs
from openpilot.tesla.ui.pages.base import ListPage

REFRESH_DESC = "Download the plugin list from github.com/onemiless/xpilot-plugins."


class StorePage(ListPage):
  def __init__(self):
    super().__init__()
    self.jobs = StoreJobs(ui_state.is_offroad)
    self.ids: set[str] = set()
    jobs = self.jobs
    self.add(ListItem(lambda: f"Refresh: {'working...' if jobs.busy else jobs.status}", description=REFRESH_DESC,
                      action_item=ButtonAction("REFRESH", enabled=lambda: not jobs.busy),
                      callback=lambda: jobs.run(jobs.fetch)))

  def _update_state(self):
    super()._update_state()
    jobs = self.jobs
    if not jobs.dirty:
      return
    jobs.dirty = False
    for entry in jobs.entries:
      if entry.id in self.ids:
        continue
      self.ids.add(entry.id)
      pid = entry.id
      current = lambda pid=pid: jobs.current(pid)  # noqa: E731
      self.add(ListItem(lambda c=current, e=entry: f"{e.name}  ·  {jobs.row_value(c() or e)}",
                        description=f"{entry.description} — {entry.author}, {entry.category}, {entry.id}",
                        action_item=ButtonAction(lambda c=current, e=entry: jobs.action(c() or e), enabled=lambda pid=pid: jobs.can_act(pid)),
                        callback=lambda pid=pid: jobs.run(lambda: jobs.act(pid))))

  def show_event(self):
    super().show_event()
