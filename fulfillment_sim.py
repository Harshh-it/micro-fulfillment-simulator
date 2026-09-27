"""
Mini Automated Micro-Fulfillment Simulator
============================================
Simulates the core loop of your prototype concept, purely in software:

    ORDER RECEIVED
      -> command sent in parallel to each product's dispensing module
      -> module runs its SENSE -> DECIDE -> ACTUATE -> CONFIRM loop
      -> dispensed item travels down that module's local lane
      -> item merges onto the shared main conveyor line
      -> all items converge at the packing station
      -> order marked READY FOR PACKING

No hardware needed. This is meant to let you see and demo the *logic* of the
whole system (parallel dispensing across categories/machines, jam/retry
handling, multi-lane merge onto one main line, consolidation timing) before
you build a single physical module.

Run in VS Code:
    1. Open this folder in VS Code.
    2. Open a terminal (Terminal > New Terminal).
    3. Run:  python fulfillment_sim.py
    4. When prompted, type product codes like:  A1,B2,C1,D1
       (or just press Enter for a demo order)

No external packages required — standard library only.
"""

import threading
import time
import random
import queue
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# 1. CATALOG — SKUs grouped into dispensing modules (categories/machines)
# ---------------------------------------------------------------------------

@dataclass
class SKU:
    sku_id: str
    name: str
    module_id: str
    dispense_time: float        # seconds - mechanism time to release 1 unit
    lane_transit_time: float    # seconds - module's local lane -> main merge point


@dataclass
class Module:
    module_id: str
    name: str
    mechanism: str
    jam_probability: float = 0.12   # ~1 in 8 dispenses hits a simulated jam, to show retry logic


CATALOG: Dict[str, SKU] = {
    "A1": SKU("A1", "Shampoo 200ml", "MOD-A", dispense_time=1.2, lane_transit_time=1.5),
    "A2": SKU("A2", "Coke 500ml",    "MOD-A", dispense_time=1.0, lane_transit_time=1.5),
    "B1": SKU("B1", "Toothpaste",    "MOD-B", dispense_time=0.8, lane_transit_time=1.2),
    "B2": SKU("B2", "Soap Bar",      "MOD-B", dispense_time=0.7, lane_transit_time=1.2),
    "C1": SKU("C1", "Chips Packet",  "MOD-C", dispense_time=0.6, lane_transit_time=1.0),
    "C2": SKU("C2", "Biscuits Pack", "MOD-C", dispense_time=0.6, lane_transit_time=1.0),
    "D1": SKU("D1", "Rice 1kg",      "MOD-D", dispense_time=1.8, lane_transit_time=2.0),
}

MODULES: Dict[str, Module] = {
    "MOD-A": Module("MOD-A", "Module A - Bottles", "Servo Gate"),
    "MOD-B": Module("MOD-B", "Module B - Boxes",   "Belt Pusher"),
    "MOD-C": Module("MOD-C", "Module C - Pouches", "Drop Chute"),
    "MOD-D": Module("MOD-D", "Module D - Bulk",    "Pneumatic Ram"),
}

MAIN_LINE_TRANSIT = 1.0            # seconds: merge junction -> packing station
MANUAL_PICK_TIME_PER_ITEM = 25.0   # seconds: illustrative human picker baseline per item


# ---------------------------------------------------------------------------
# 2. ORDER MODEL
# ---------------------------------------------------------------------------

@dataclass
class OrderItem:
    sku: SKU
    status: str = "pending"     # pending / dispensing / dispensed / on_lane / at_merge / failed
    attempts: int = 0
    arrived_at: Optional[float] = None


@dataclass
class Order:
    order_id: str
    items: List[OrderItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. SIMULATION ENGINE
# ---------------------------------------------------------------------------

print_lock = threading.Lock()
start_time: Optional[float] = None


def log(msg: str, tag: str = "INFO") -> None:
    elapsed = time.time() - start_time
    with print_lock:
        print(f"[{elapsed:6.2f}s] [{tag:8s}] {msg}")


def dispense_item(order_item: OrderItem, merge_queue: "queue.Queue[OrderItem]") -> None:
    """One module's SENSE -> DECIDE -> ACTUATE -> CONFIRM loop for a single item."""
    sku = order_item.sku
    module = MODULES[sku.module_id]

    while True:
        order_item.attempts += 1
        order_item.status = "dispensing"
        log(f"CMD -> {module.name}: dispense '{sku.name}' (attempt {order_item.attempts})",
            tag=module.module_id)

        time.sleep(0.15)               # simulated signal transmission delay
        time.sleep(sku.dispense_time)  # simulated motor/actuation time

        if random.random() < module.jam_probability:
            log(f"JAM at {module.name} while dispensing '{sku.name}' - clearing and retrying",
                tag="FAULT")
            order_item.status = "failed"
            time.sleep(0.5)             # simulated jam-clear delay before retry
            continue

        break

    order_item.status = "dispensed"
    log(f"{module.name}: '{sku.name}' dispensed OK - sensor confirms item present",
        tag=module.module_id)

    order_item.status = "on_lane"
    time.sleep(sku.lane_transit_time)  # travel down this module's own lane

    order_item.status = "at_merge"
    order_item.arrived_at = time.time()
    log(f"'{sku.name}' reached MAIN MERGE LINE from {module.name}", tag="MERGE")
    merge_queue.put(order_item)


def run_order(order: Order) -> None:
    global start_time
    start_time = time.time()

    print("\n" + "=" * 72)
    print(f" ORDER {order.order_id} RECEIVED - {len(order.items)} item(s)")
    for it in order.items:
        print(f"   - {it.sku.name}  (from {MODULES[it.sku.module_id].name})")
    print("=" * 72 + "\n")

    merge_queue: "queue.Queue[OrderItem]" = queue.Queue()
    threads = []
    for order_item in order.items:
        t = threading.Thread(target=dispense_item, args=(order_item, merge_queue), daemon=True)
        threads.append(t)
        t.start()

    received: List[OrderItem] = []
    while len(received) < len(order.items):
        item = merge_queue.get()
        time.sleep(MAIN_LINE_TRANSIT)     # shared main line -> packing station
        received.append(item)
        log(f"[{len(received)}/{len(order.items)}] items now at PACKING STATION "
            f"(latest: {item.sku.name})", tag="PACK")

    for t in threads:
        t.join()

    total_time = time.time() - start_time
    manual_time = len(order.items) * MANUAL_PICK_TIME_PER_ITEM

    print("\n" + "-" * 72)
    print(f" ORDER {order.order_id} READY FOR PACKING")
    print(f" Automated fulfillment time : {total_time:6.2f} sec")
    print(f" Manual picker baseline*    : {manual_time:6.2f} sec "
          f"(~{MANUAL_PICK_TIME_PER_ITEM:.0f}s/item walking+picking)")
    if manual_time > 0:
        pct = (1 - total_time / manual_time) * 100
        print(f" Time saved                 : {manual_time - total_time:6.2f} sec ({pct:.0f}% faster)")
    print("-" * 72)
    print(" * Manual baseline is an illustrative comparison figure, not a measured benchmark.\n")


# ---------------------------------------------------------------------------
# 4. ORDER-ENTRY MENU
# ---------------------------------------------------------------------------

def print_catalog() -> None:
    print("\nAvailable products:")
    by_module: Dict[str, List[SKU]] = {}
    for sku in CATALOG.values():
        by_module.setdefault(sku.module_id, []).append(sku)

    for module_id, skus in by_module.items():
        print(f"\n {MODULES[module_id].name}  [{MODULES[module_id].mechanism}]")
        for sku in skus:
            print(f"   {sku.sku_id:4s} - {sku.name}")


def build_order_interactively() -> Order:
    print_catalog()
    print("\nEnter product codes for this order, comma-separated (e.g. A1,B2,C1).")
    try:
        raw = input("Order items (Enter for demo order): ").strip().upper()
    except EOFError:
        raw = ""

    codes = [c.strip() for c in raw.split(",") if c.strip()]
    items: List[OrderItem] = []
    for code in codes:
        if code in CATALOG:
            items.append(OrderItem(sku=CATALOG[code]))
        else:
            print(f"  (skipping unknown code '{code}')")

    if not items:
        print("Using a demo order: Shampoo + Chips + Soap + Rice")
        items = [
            OrderItem(sku=CATALOG["A1"]),
            OrderItem(sku=CATALOG["C1"]),
            OrderItem(sku=CATALOG["B2"]),
            OrderItem(sku=CATALOG["D1"]),
        ]

    order_id = f"ORD-{random.randint(1000, 9999)}"
    return Order(order_id=order_id, items=items)


if __name__ == "__main__":
    random.seed()  # vary jam events each run; pass an int here instead to reproduce a run exactly
    demo_order = build_order_interactively()
    run_order(demo_order)
