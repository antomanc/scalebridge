#include "scale_decoders.h"

#define LB_KG 0.45359237f

static uint16_t u16le(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

const char *sb_decoder_id(sb_decoder_t decoder) {
    switch (decoder) {
    case SB_DECODER_XIAOMI_MI_SCALE_2:
        return "xiaomi_mi_scale_2";
    case SB_DECODER_XIAOMI_MI_BODY_COMPOSITION:
        return "xiaomi_mi_body_composition";
    default:
        return "";
    }
}

/* Mi Smart Scale 2 (0x181D), 10 bytes: flags, weight u16le, then a timestamp we ignore. */
static bool decode_mi_scale_2(const uint8_t *d, size_t len, sb_reading_t *out) {
    if (len != 10) return false;
    uint8_t flags = d[0];
    uint16_t raw = u16le(&d[1]);
    if (raw == 0) return false;
    if (flags & 0x01) {
        out->weight_kg = raw * 0.01f * LB_KG;
    } else if (flags & 0x10) {
        out->weight_kg = raw * 0.01f * 0.5f; /* jin */
    } else {
        out->weight_kg = raw * 0.005f;
    }
    out->stable = flags & 0x20;
    out->complete = out->stable;
    out->load_removed = flags & 0x80;
    out->impedance_ohm = -1;
    return true;
}

/* Mi Body Composition Scale (0x181B), 13 bytes: unit, flags, timestamp, impedance, weight. */
static bool decode_mi_body_composition(const uint8_t *d, size_t len, sb_reading_t *out) {
    if (len != 13) return false;
    uint8_t unit = d[0], flags = d[1];
    uint16_t raw = u16le(&d[11]);
    if (raw == 0) return false;
    out->weight_kg = unit == 0x03 ? raw * 0.01f * LB_KG : raw * 0.005f;
    out->impedance_ohm = -1;
    if (flags & 0x02) {
        uint16_t imp = u16le(&d[9]);
        if (imp > 0 && imp < 3000) out->impedance_ohm = imp;
    }
    out->stable = flags & 0x20;
    out->load_removed = flags & 0x80;
    out->complete = out->stable && (out->impedance_ohm >= 0 || out->load_removed);
    return true;
}

sb_decoder_t sb_decode(uint16_t service_uuid16, const uint8_t *data, size_t len, sb_reading_t *out) {
    sb_reading_t r;
    if (service_uuid16 == 0x181D && decode_mi_scale_2(data, len, &r)) {
        *out = r;
        return SB_DECODER_XIAOMI_MI_SCALE_2;
    }
    if (service_uuid16 == 0x181B && decode_mi_body_composition(data, len, &r)) {
        *out = r;
        return SB_DECODER_XIAOMI_MI_BODY_COMPOSITION;
    }
    return SB_DECODER_NONE;
}
