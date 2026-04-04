#pragma once
#include <stddef.h>
#include <stdint.h>

/*
 * A single recognised text region.
 * Coordinates are top-left-origin, normalised to [0, 1].
 * `text` is heap-allocated and owned by the OcrResultList that contains it.
 */
typedef struct {
    char  *text;
    double x;
    double y;
    double width;
    double height;
} OcrItem;

typedef struct {
    OcrItem *items;
    int      count;
} OcrResultList;

/* Release all memory owned by a result list. */
void ocr_result_free(OcrResultList result);

/*
 * Return a heap-allocated NULL-terminated array of BCP-47 language codes
 * supported by the Vision OCR engine.
 * Caller must pass the pointer to ocr_langs_free() when done.
 */
char **ocr_get_supported_langs(void);
void   ocr_langs_free(char **langs);

/*
 * Run OCR on a raw BGRA8 pixel buffer (tightly packed, no row padding,
 * i.e. buf_len == width * height * 4).
 *
 * roi_* are normalised top-left-origin coordinates.
 * Pass (0, 0, 1, 1) to scan the full image.
 *
 * langs / custom_words may be NULL when the respective count is 0.
 * custom_words is only applied when high_accuracy != 0.
 */
OcrResultList ocr_detect_bgra8(
    const uint8_t *bgra8,
    int            width,
    int            height,
    double         roi_x,
    double         roi_y,
    double         roi_w,
    double         roi_h,
    int            high_accuracy,
    const char   **langs,
    int            lang_count,
    const char   **custom_words,
    int            word_count
);

/*
 * Run OCR on an encoded image file loaded into memory (JPEG, PNG, HEIC, …).
 * roi_* and accuracy / language semantics are identical to ocr_detect_bgra8.
 */
/*
 * out_width and out_height are set to the decoded image dimensions in pixels.
 * Both are set to 0 on failure.
 */
OcrResultList ocr_detect_image(
    const uint8_t *data,
    size_t         data_len,
    double         roi_x,
    double         roi_y,
    double         roi_w,
    double         roi_h,
    int            high_accuracy,
    const char   **langs,
    int            lang_count,
    const char   **custom_words,
    int            word_count,
    int           *out_width,
    int           *out_height
);
