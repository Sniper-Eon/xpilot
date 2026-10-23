"""SP Model Manager: the default role:perception.model plugin. SP's models_manager, modeld, modeld_tinygrad and
modeld_warmup stay in process_config.py; fork_processes.py runs them only while no other plugin owns the role."""
from openpilot.tesla.plugin import Plugin


class SpModels(Plugin):
  pass
