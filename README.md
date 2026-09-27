# Micro-Fulfillment Picking Simulator

A small simulation exploring whether automated modular picking (cabinets → shuttles →
distribution belt → packing stations) could reduce item-collection time in quick-commerce
dark stores — inspired by watching an office vending machine dispense a can in under 2 seconds.

🔗 **[Live demo →](https://harshh-it.github.io/micro-fulfillment-simulator/fulfillment_flow.html)**

## What it demonstrates
- Sense → Decide → Actuate → Confirm control loop per pick (not "assume success")
- Nearest-neighbour shuttle movement to minimize travel per cabinet
- Dynamic order-to-station assignment based on least total travel
- Concurrent order handling across 4 packing stations, with queueing when all are busy
- Jam/failure simulation with automatic retry

## Status
Early-stage prototype — not yet connected to real hardware. Next step: physical build
with ESP32 + sensors.
