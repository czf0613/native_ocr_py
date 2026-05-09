#pragma once
#include <stddef.h>
#include <stdint.h>

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

void ocr_result_free(OcrResultList result);

char **ocr_get_supported_langs(void);
void   ocr_langs_free(char **langs);

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
