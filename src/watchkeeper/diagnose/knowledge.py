"""What an operator needs next to a diagnosis: why it matters, the first thing to check by hand, and the failure family.

Texts are ours, written from the benchmark documentation (TECHNICAL_MODEL.md) and standard pump practice; they are not model output.
`check` is a verification step that takes minutes and can overturn the diagnosis. `recommended_action` stays the maintenance step.
"""
from __future__ import annotations

FAMILY = {
    "SUCTION_STRAINER_CLOGGING": "suction", "CAVITATION": "suction", "AIR_ENTRAINMENT": "suction",
    "DISCHARGE_RESTRICTION": "discharge", "IMPELLER_WEAR": "discharge",
    "BEARING_WEAR": "mechanical", "MISALIGNMENT": "mechanical", "IMBALANCE": "mechanical",
    "SENSOR_DRIFT": "instrument", "SENSOR_STUCK": "instrument", "SENSOR_CALIBRATION_SHIFT": "instrument",
    "SENSOR_NOISE_SPIKES": "instrument", "COMMUNICATION_LOSS": "gateway", "UNKNOWN": "unknown",
}

KNOWLEDGE = {
    "SUCTION_STRAINER_CLOGGING": {
        "consequence": "Cooling flow falls and the drive raises speed to compensate. If it continues, suction pressure drops far enough to cause cavitation.",
        "check": "Read the suction pressure locally and compare it with the transmitter. If a strainer differential gauge exists, read it."},
    "CAVITATION": {
        "consequence": "Vapour bubbles erode the impeller and cut head and flow. Vibration and noise rise within minutes.",
        "check": "Listen at the pump for gravel-like noise and check suction level and strainer. Note whether it worsens at high flow."},
    "AIR_ENTRAINMENT": {
        "consequence": "Head and flow become erratic, which can trip cooling alarms on the loads.",
        "check": "Check tank or sea-chest level and look for air in the suction line or at the vent."},
    "DISCHARGE_RESTRICTION": {
        "consequence": "Flow and heat removal fall, the pump moves left of its best point and wears faster.",
        "check": "Confirm discharge valve positions and read the heat exchanger pressure drop locally."},
    "IMPELLER_WEAR": {
        "consequence": "The pump delivers less head at the same speed, so efficiency falls and energy is wasted.",
        "check": "Compare discharge pressure at a known operating point with the pump curve or an earlier reading."},
    "BEARING_WEAR": {
        "consequence": "Failure can follow within days to weeks. A seized bearing stops the pump and can damage the shaft or seal.",
        "check": "Take a handheld vibration and temperature reading on the bearing housing and listen for roughness."},
    "MISALIGNMENT": {
        "consequence": "Bearings and the coupling wear faster and temperatures rise, most often after recent work on the pump or motor.",
        "check": "Check the coupling guard and alignment records for recent work, and feel the coupling-end bearing temperature."},
    "IMBALANCE": {
        "consequence": "Vibration at running speed grows with speed and shortens bearing and seal life.",
        "check": "Inspect the impeller for deposits or damage; compare vibration at two speeds if the drive allows."},
    "SENSOR_DRIFT": {
        "consequence": "A drifting instrument can trigger an unnecessary repair, or hide a real fault that it should reveal.",
        "check": "Compare the transmitter with a local gauge or a second instrument on the same quantity."},
    "SENSOR_STUCK": {
        "consequence": "The reading no longer follows the process, so alarms and this system are blind on that quantity.",
        "check": "Check the instrument and wiring; change the process slightly (valve or speed) and see whether the reading moves."},
    "SENSOR_CALIBRATION_SHIFT": {
        "consequence": "Readings are offset, which can trigger an unnecessary repair or mask a real fault.",
        "check": "Verify the transmitter against a reference gauge at standstill and at running pressure."},
    "SENSOR_NOISE_SPIKES": {
        "consequence": "Spikes cause nuisance alarms and make the signal unreliable for diagnosis.",
        "check": "Check wiring, shielding and power supply of the transmitter; compare with a local gauge."},
    "COMMUNICATION_LOSS": {
        "consequence": "While data is missing no fault can be assessed, and an incident can develop unseen.",
        "check": "Check the gateway and network link; confirm whether the local displays still update."},
    "UNKNOWN": {
        "consequence": "Something is off, but the cause is unclear, so the risk cannot be graded.",
        "check": "Read the main signals locally and compare them with the trends shown here before deciding."},
}


def knowledge(fault_type: str) -> dict:
    return KNOWLEDGE.get(fault_type, KNOWLEDGE["UNKNOWN"])
