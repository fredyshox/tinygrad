# create a diff of two schedule graphs
import logging
from collections import defaultdict
from typing import DefaultDict, List, Set, Tuple
from test.external.process_replay.utils import print_diff
from tinygrad.engine.schedule import LBScheduleItem, ScheduleItem
from tinygrad.helpers import DEBUG, Context, colored, dedup, getenv
from tinygrad.lazy import LazyBuffer
from tinygrad.ops import LazyOp
from tinygrad.engine.realize import CompiledRunner, lower_schedule_item

def diff_schedule(s:List[Tuple[DefaultDict[LBScheduleItem, List[LBScheduleItem]], DefaultDict[LBScheduleItem, int]]]) -> int:
  si_for_buf: DefaultDict[LazyBuffer, List[ScheduleItem]] = defaultdict(list)
  for _,in_degree in s:
    for lsi in in_degree:
      for buf in lsi.outputs:
        si_for_buf[buf].append(ScheduleItem(lsi.ast, tuple(x.buffer for x in lsi.outputs+lsi.inputs if x.size != 0), lsi.metadata))
  changed = 0
  seen_diffs: Set[Tuple[LazyOp, ...]] = set()
  for buf, si in si_for_buf.items():
    asts = tuple(dedup([x.ast for x in si]))
    # kernels didn't change
    if len(si) > 1 and len(asts) == 1: continue
    if asts in seen_diffs: continue
    seen_diffs.add(asts)
    changed += 1
    if len(asts) == 1:
      print(f"{buf} folded in the second schedule")
    else: print_si_diff(si[0], si[1])
  if DEBUG >= 1: print(f"*** process replay: {changed} unique kernel{'s' if changed>1 else ''} changed")
  return changed

def print_si_diff(si0:ScheduleItem, si1:ScheduleItem):
  logging.basicConfig(level=logging.INFO)
  ei0 = lower_schedule_item(si0)
  ei1 = lower_schedule_item(si1)
  assert isinstance(ei0.prg, CompiledRunner) and isinstance(ei1.prg, CompiledRunner)
  print_diff(si0.ast, si1.ast)
  print_diff(ei0.prg.p.src, ei1.prg.p.src)
  # TODO: create new Buffers for process replay
  if getenv("TIMING"):
    with Context(DEBUG=2):
      tm0 = ei0.run(wait=True)
      tm1 = ei1.run(wait=True)
    assert tm0 is not None and tm1 is not None
    tm_diff = ((tm0 - tm1) / tm0) * 100
    if tm_diff > 0: print(colored(f"{tm_diff:.2f}% faster", "green"))
    else: print(colored(f"{tm_diff:,.2f}% slower", "red"))
