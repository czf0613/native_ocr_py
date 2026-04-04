#import <Vision/Vision.h>
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>
#include <stdlib.h>
#include <string.h>
#include "apple_ocr.h"

/* ---- Memory management ---------------------------------------- */

void ocr_result_free(OcrResultList result) {
    for (int i = 0; i < result.count; i++) {
        free(result.items[i].text);
    }
    free(result.items);
}

void ocr_langs_free(char **langs) {
    if (!langs) return;
    for (int i = 0; langs[i]; i++) {
        free(langs[i]);
    }
    free(langs);
}

/* ---- Internal helpers ----------------------------------------- */

/*
 * Convert a Vision results array to OcrResultList.
 * Vision uses bottom-left-origin normalised coordinates; we convert to
 * top-left-origin before storing.
 */
static OcrResultList extract_results(NSArray<VNRecognizedTextObservation *> *observations) {
    OcrResultList result = {NULL, 0};
    if (!observations || observations.count == 0) return result;

    result.items = (OcrItem *)malloc(observations.count * sizeof(OcrItem));
    if (!result.items) return result;

    for (VNRecognizedTextObservation *obs in observations) {
        VNRecognizedText *candidate = [[obs topCandidates:1] firstObject];
        if (!candidate || candidate.string.length == 0) continue;

        result.items[result.count].text = strdup(candidate.string.UTF8String);

        /* Convert from Vision's bottom-left origin to top-left origin */
        CGRect bbox = obs.boundingBox;
        result.items[result.count].x      = bbox.origin.x;
        result.items[result.count].y      = 1.0 - (bbox.origin.y + bbox.size.height);
        result.items[result.count].width  = bbox.size.width;
        result.items[result.count].height = bbox.size.height;

        result.count++;
    }

    return result;
}

/*
 * Configure a VNRecognizeTextRequest, run it through the given handler,
 * and return the extracted results.
 * roi_* are top-left-origin; converted to Vision's bottom-left-origin internally.
 */
static OcrResultList run_request(
    VNImageRequestHandler *handler,
    double roi_x, double roi_y, double roi_w, double roi_h,
    int high_accuracy,
    const char **langs, int lang_count,
    const char **custom_words, int word_count
) {
    OcrResultList empty = {NULL, 0};

    VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];

    request.recognitionLevel = high_accuracy
        ? VNRequestTextRecognitionLevelAccurate
        : VNRequestTextRecognitionLevelFast;

    /* Vision ROI is bottom-left-origin */
    request.regionOfInterest = CGRectMake(roi_x, 1.0 - roi_y - roi_h, roi_w, roi_h);

    if (lang_count > 0) {
        NSMutableArray<NSString *> *langArray = [NSMutableArray arrayWithCapacity:lang_count];
        for (int i = 0; i < lang_count; i++) {
            [langArray addObject:[NSString stringWithUTF8String:langs[i]]];
        }
        request.recognitionLanguages = langArray;
    }

    /* custom_words only takes effect in accurate mode */
    if (word_count > 0 && high_accuracy) {
        NSMutableArray<NSString *> *wordArray = [NSMutableArray arrayWithCapacity:word_count];
        for (int i = 0; i < word_count; i++) {
            [wordArray addObject:[NSString stringWithUTF8String:custom_words[i]]];
        }
        request.customWords = wordArray;
    }

    NSError *error = nil;
    if (![handler performRequests:@[request] error:&error]) {
        return empty;
    }

    return extract_results(request.results);
}

/* ---- Public API ----------------------------------------------- */

char **ocr_get_supported_langs(void) {
    VNRecognizeTextRequest *req = [[VNRecognizeTextRequest alloc] init];
    req.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
    NSError *error = nil;
    NSArray<NSString *> *langs = [req supportedRecognitionLanguagesAndReturnError:&error];

    if (error || !langs) {
        char **empty = (char **)malloc(sizeof(char *));
        empty[0] = NULL;
        return empty;
    }

    char **result = (char **)malloc((langs.count + 1) * sizeof(char *));
    for (NSUInteger i = 0; i < langs.count; i++) {
        result[i] = strdup(langs[i].UTF8String);
    }
    result[langs.count] = NULL;
    return result;
}

OcrResultList ocr_detect_bgra8(
    const uint8_t *bgra8,
    int width, int height,
    double roi_x, double roi_y, double roi_w, double roi_h,
    int high_accuracy,
    const char **langs, int lang_count,
    const char **custom_words, int word_count
) {
    OcrResultList empty = {NULL, 0};

    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    CGDataProviderRef provider = CGDataProviderCreateWithData(
        NULL, bgra8, (size_t)(width * height * 4), NULL
    );
    CGImageRef cgImage = CGImageCreate(
        (size_t)width, (size_t)height,
        8, 32, (size_t)(width * 4),
        colorSpace,
        kCGBitmapByteOrder32Little | kCGImageAlphaPremultipliedFirst,
        provider,
        NULL, false, kCGRenderingIntentDefault
    );
    CGColorSpaceRelease(colorSpace);
    CGDataProviderRelease(provider);

    if (!cgImage) return empty;

    VNImageRequestHandler *handler = [[VNImageRequestHandler alloc]
        initWithCGImage:cgImage options:@{}];
    CGImageRelease(cgImage);

    return run_request(handler, roi_x, roi_y, roi_w, roi_h,
                       high_accuracy, langs, lang_count, custom_words, word_count);
}

OcrResultList ocr_detect_image(
    const uint8_t *data, size_t data_len,
    double roi_x, double roi_y, double roi_w, double roi_h,
    int high_accuracy,
    const char **langs, int lang_count,
    const char **custom_words, int word_count,
    int *out_width, int *out_height
) {
    OcrResultList empty = {NULL, 0};
    *out_width  = 0;
    *out_height = 0;

    NSData *nsData = [NSData dataWithBytesNoCopy:(void *)data length:data_len freeWhenDone:NO];
    CGImageSourceRef imageSource = CGImageSourceCreateWithData((__bridge CFDataRef)nsData, NULL);
    if (!imageSource) return empty;

    CGImageRef cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, NULL);
    CFRelease(imageSource);
    if (!cgImage) return empty;

    *out_width  = (int)CGImageGetWidth(cgImage);
    *out_height = (int)CGImageGetHeight(cgImage);

    VNImageRequestHandler *handler = [[VNImageRequestHandler alloc]
        initWithCGImage:cgImage options:@{}];
    CGImageRelease(cgImage);

    return run_request(handler, roi_x, roi_y, roi_w, roi_h,
                       high_accuracy, langs, lang_count, custom_words, word_count);
}
