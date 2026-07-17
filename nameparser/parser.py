"""v1 import-path preservation (migration spec §3): the 2.0 HumanName
facade lives in nameparser._facade. This module is deleted in 3.0.
"""
from nameparser._facade import HumanName as HumanName

__all__ = ["HumanName"]
