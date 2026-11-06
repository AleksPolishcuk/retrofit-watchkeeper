# Business case for one retrofitted pump (synthetic scenario)

Every money figure is an assumption. The detection figures are measured on the synthetic benchmark with leave-one-asset-out. This shows how the numbers combine, not a saving at any real site.

## Measured inputs

| Measure | Value | Meaning |
|---|---|---|
| Event recall | 0.80 | share of the 35 scored events that received an alert in their window |
| Found before the conventional alarm limit | **0.56** | of the events that ever reach a limit (9 of 35), 5 were caught before it |
| False-alert episodes per pump-day | 0.063 | 4 episodes over 63 pump-days |
| Repeat alerts beyond the free reminder per pump-day | 0.079 | 5 repeats on problems already flagged |

Lead time for the 5 events caught early: 0.3 h, 13.9 h, 16.3 h, 97.7 h, 113.9 h. Slow mechanical faults (bearing wear, imbalance, strainer clogging) give hours to days of warning. Fast hydraulic episodes such as cavitation give almost none: the alert comes minutes after the limit, so there the value is the diagnosis, not the lead time.

## Assumptions

| Input | Value | Unit | Basis |
|---|---|---|---|
| events per year | 0.6 | 1/yr | developing faults per duty pump that would otherwise end in an unplanned stop |
| unplanned stop h | 10 | h | detection by failure, diagnosis, parts, repair |
| planned stop h | 3 | h | the same work prepared and done in a planned window |
| downtime cost eur h | 1500 | EUR/h | production loss of a mid-size line with no redundant pump |
| repair unplanned eur | 9000 | EUR | within a typical EUR 3-15 k pump overhaul range (itself an estimate) |
| repair planned eur | 4000 | EUR | damage limited when caught early |
| false alert cost eur | 120 | EUR | about 1.5 h of technician time to check one false alert |
| repeat alert cost eur | 30 | EUR | a repeat on a problem already known is a glance, not a check (our assumption) |
| capex eur | 4500 | EUR | BOM option B about EUR 2.1-2.4 k from list prices plus cabling, enclosure and installation |
| opex eur yr | 700 | EUR/yr | connectivity, software maintenance, battery and sensor replacement |

## Base case (no redundant pump, downtime EUR 1,500 per hour)

| | Organizers' convention (all alerts cost EUR 120) | Refined (repeats cost EUR 30) |
|---|---|---|
| Avoided downtime and repair per year | EUR 5,167 | EUR 5,167 |
| Alert handling per year | EUR 6,257 | EUR 3,650 |
| Operating cost per year | EUR 700 | EUR 700 |
| **Net per year** | **EUR -1,790** | **EUR 817** |
| Payback on EUR 4,500 | never | 5.5 yr |

**Reading.** At the current alert rate the base case is not positive under the organizers' convention. The cost of checking alerts (EUR 6,257 per year) is larger than the avoided cost (EUR 5,167). Fewer false alerts and a higher share found before the limit are what turn it positive, and the sections below show how far each one has to move.

## By type of site

| Site | Downtime EUR/h | Faults/yr | Net EUR/yr (refined) | Payback |
|---|---|---|---|---|
| Ship seawater pump with a healthy standby | 0 | 0.3 | -3,517 | never |
| Cooling-tower circulation pump | 400 | 0.6 | -1,750 | never |
| Hot process-water transfer pump | 600 | 0.6 | -1,283 | never |
| Process pump with no redundancy (organizers' example) | 1,500 | 0.6 | 817 | 5.5 yr |

A standby pump takes the downtime term to zero, so the case there rests on avoided repair cost, crew time and energy, and does not pay back on monitoring alone.

## What has to move for a 5-year payback (refined convention, one input at a time)

- Downtime cost: about EUR 1,536 per hour (now 1,500).
- False-alert episodes per pump-day: below 0.062 (now 0.063).
- Share found before the limit: 0.56 (now 0.56).

## Sensitivity (refined convention)

| Input | Low | High | Net EUR/yr low | Net EUR/yr high |
|---|---|---|---|---|
| events per year | 0.2 | 1.2 | -2,628 | 5,983 |
| caught | 0.3 | 0.95 | -1,560 | 4,485 |
| false per day | 0 | 0.3 | 3,598 | -9,542 |
| downtime cost eur h | 0 | 5000 | -2,683 | 8,983 |
| repair unplanned eur | 5000 | 15000 | -517 | 2,817 |
| capex eur | 2000 | 12000 | 817 | 817 |

## What each retrofit level sees (measured on the dev pumps)

| Instrumentation | Installed cost (assumption) | Events | Detected | Right type |
|---|---|---|---|---|
| Level 0: existing signals only (edge box + read-only integration) | EUR 2,000 | 5 | 3 | 2 |
| Level 1: + suction pressure transmitter + wireless vibration point | EUR 3,500 | 15 | 11 | 9 |
| Level 2: wired vibration, power and flow metering (option A/B) | EUR 4,500 | 15 | 14 | 7 |

Each level has only a handful of events (2 to 4 pumps), so these counts show a direction and do not rank the levels with confidence.

## Honest limits

- Synthetic data and assumed costs. Faults per year, downtime cost and repair cost drive the result more than the detector does.
- Only 9 of the 35 events reach a conventional limit, so "found before the limit" rests on 9 events (5 caught).
- The alert rate is the weakest number. Lowering false alerts is worth more than raising recall at this point.
- No claim of certified safety, class approval or proven savings.
