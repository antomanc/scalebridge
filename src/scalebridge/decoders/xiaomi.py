"""Xiaomi Mi scales. They broadcast measurements in advertisements; no pairing is needed.

Byte layouts follow ESPHome's `xiaomi_miscale` component and were checked against
captures from an XMTZC04HM.
"""

from __future__ import annotations

from scalebridge.models import Advertisement, Reading

LB_KG = 0.45359237


def uuid16(short: int) -> str:
    return f"0000{short:04x}-0000-1000-8000-00805f9b34fb"


class MiScale:
    """Mi Smart Scale 2 (XMTZC01HM, XMTZC04HM): weight only, standard Weight Scale service.

    Payload (10 bytes): flags, weight u16le, year u16le, month, day, hour, minute, second.
    The scale's clock is often never set, so its timestamp is ignored.
    """

    id = "xiaomi_mi_scale_2"
    model = "Xiaomi Mi Smart Scale 2"
    service_uuid = uuid16(0x181D)

    def decode(self, payload: bytes, adv: Advertisement) -> Reading | None:
        if len(payload) != 10:
            return None
        flags = payload[0]
        raw = int.from_bytes(payload[1:3], "little")
        if raw == 0:
            return None
        if flags & 0x01:
            weight = raw * 0.01 * LB_KG
        elif flags & 0x10:
            weight = raw * 0.01 * 0.5  # jin (市斤)
        else:
            weight = raw * 0.005
        stable = bool(flags & 0x20)
        return Reading(
            address=adv.address,
            model=self.model,
            weight_kg=round(weight, 2),
            received_at=adv.received_at,
            stable=stable,
            complete=stable,
            load_removed=bool(flags & 0x80),
        )


class MiBodyCompositionScale:
    """Mi Body Composition Scale 1/2 (XMTZC02HM, XMTZC05HM): weight plus impedance.

    Payload (13 bytes): unit, flags, year u16le, month, day, hour, minute, second,
    impedance u16le, weight u16le. Impedance arrives a few seconds after the weight settles.
    """

    id = "xiaomi_mi_body_composition"
    model = "Xiaomi Mi Body Composition Scale"
    service_uuid = uuid16(0x181B)

    def decode(self, payload: bytes, adv: Advertisement) -> Reading | None:
        if len(payload) != 13:
            return None
        unit, flags = payload[0], payload[1]
        raw = int.from_bytes(payload[11:13], "little")
        if raw == 0:
            return None
        weight = raw * 0.01 * LB_KG if unit == 0x03 else raw * 0.005
        impedance = int.from_bytes(payload[9:11], "little") if flags & 0x02 else None
        if impedance is not None and not 0 < impedance < 3000:
            impedance = None
        stable = bool(flags & 0x20)
        removed = bool(flags & 0x80)
        return Reading(
            address=adv.address,
            model=self.model,
            weight_kg=round(weight, 2),
            received_at=adv.received_at,
            stable=stable,
            complete=stable and (impedance is not None or removed),
            load_removed=removed,
            impedance_ohm=impedance,
        )
