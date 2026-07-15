# Mission vision scenarios

Operational UUV profiles for characterization — not release gates. These missions
exercise the same hybrid navigation stack as integration validation, but with
routes and dropout patterns aligned to littoral insertion and long-range transit.

## Scenarios

| Name | Domain | Profile |
|------|--------|---------|
| `shore_beach_landing` | harbor | Shore launch → submerged coastal transit → beach touchdown |
| `ship_to_shore_insertion` | harbor | Mothership drop offshore → submerged ingress to surf zone |
| `shore_to_shore_transfer` | harbor | Coastal shuttle with mid-transit GPS denial |
| `harbor_to_open_ocean_recharge` | harbor | Harbor exit with staged surface recharge legs |
| `stealth_solar_transit` | deep | Long submerged legs + periodic surface GPS/solar sniffs |
| `hydrokinetic_transit` | deep | Fully submerged GPS-denied leg (flow-harvest endurance) |

Gates are intentionally looser than `VALIDATION_SCENARIOS` / `DEEP_VALIDATION_SCENARIOS`.
They answer “can we navigate this profile?” rather than “does this pass release?”

## Hydrokinetic / foil turbine charging

**Yes — small flow-harvest generators on foils or the hull are technically feasible.**

Real systems use variants of:

- **Towed or hull-mounted micro-turbines** that spin in the relative water flow
- **Propeller regeneration** when the vehicle is being carried by current
- **Dedicated hydro generators** on lifting foils or struts (analogous to ram-air
  turbines on aircraft, but driven by water speed instead of air)

Tradeoffs for a UUV:

| Factor | Effect |
|--------|--------|
| Drag | Harvested power costs speed or requires higher thrust |
| Speed | Useful power scales roughly with flow velocity cubed at small scales |
| Signature | Moving parts add acoustic and EM noise |
| Fouling | Foil-mounted hardware is exposed to biofouling in littoral water |
| Mass / volume | Competes with payload and battery capacity on small platforms |

## Power budget

Charybdis models a normalized **power budget** on hybrid harbor and deep runs.
Enable it with `PowerBudgetConfig(enabled=True)` on `HybridHarborConfig` /
`HybridDeepConfig`, or use the mission builders which attach profiles automatically.

Per-step net discharge uses hotel load + cubic propulsion + bathy pings, minus
charging from **surface solar** (`surface_charge`) or **hydro harvest**
(`hydro_charge_coeff`, with optional harvest drag). `endurance_s` is seconds to
drain from full to empty at unit net discharge.

| Mission | Charging profile |
|---------|------------------|
| `harbor_to_open_ocean_recharge` | Strong surface solar on recharge legs |
| `stealth_solar_transit` | Moderate solar on scheduled sniff waypoints |
| `hydrokinetic_transit` | Flow harvest + drag, no surface charge |
| Other littoral missions | Discharge only (short legs) |

Summaries add `final_energy_frac`, `min_energy_frac`, and `rtb_triggered` when
power is enabled. `hydrokinetic_transit` couples navigation with flow-harvest
endurance: DVL + bathymetry through a long submerged leg with no GPS fixes.

Contrast with `stealth_solar_transit`, which still surfaces on a schedule for
GPS/solar recharge.

## Quick preview (single seed)

```bash
python examples/run_mission_preview.py --scenario hydrokinetic_transit --seed 7
python examples/run_mission_preview.py --scenario shore_beach_landing
```

## Mission matrix (Monte Carlo)

```bash
python scripts/hybrid_validate_mission_matrix.py --tier engineering --allow-dirty
python scripts/hybrid_validate_mission_matrix.py --tier engineering \
  --scenarios shore_beach_landing stealth_solar_transit hydrokinetic_transit
```

Artifacts land under `artifacts/validation/<stamp>-<sha>/mission_<tier>/`.

## Pod (engineering smoke)

```bash
bash scripts/pod/pod_mission_matrix.sh
```
