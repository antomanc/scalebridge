/*
 * Scale advertisement decoders, C port of scalebridge/decoders.
 *
 * Plain C99 with no ESP-IDF dependency, so it builds for the ESP32 and on a PC,
 * where tests/test_firmware_decoders.py runs it against spec/vectors/decoders.json.
 */
#ifndef SCALE_DECODERS_H
#define SCALE_DECODERS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    SB_DECODER_NONE = 0,
    SB_DECODER_XIAOMI_MI_SCALE_2,          /* "xiaomi_mi_scale_2" */
    SB_DECODER_XIAOMI_MI_BODY_COMPOSITION, /* "xiaomi_mi_body_composition" */
} sb_decoder_t;

typedef struct {
    float weight_kg;
    bool stable;       /* the scale considers the weight settled */
    bool complete;     /* nothing more will follow for this weigh-in */
    bool load_removed;
    int32_t impedance_ohm; /* -1 when absent */
} sb_reading_t;

/* Stable string id of a decoder, matching the Python `Decoder.id`. */
const char *sb_decoder_id(sb_decoder_t decoder);

/*
 * Decode service data advertised under a 16-bit service UUID.
 * Returns SB_DECODER_NONE (and leaves *out untouched) when nothing understands it.
 */
sb_decoder_t sb_decode(uint16_t service_uuid16, const uint8_t *data, size_t len, sb_reading_t *out);

#ifdef __cplusplus
}
#endif

#endif /* SCALE_DECODERS_H */
