#define PY_SSIZE_T_CLEAN
#import <Python.h>
#import <Vision/Vision.h>
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>
#include <stdlib.h>

static const char **unpack_str_list(PyObject *list, int *out_count)
{
    Py_ssize_t n = PyList_GET_SIZE(list);
    const char **arr = (const char **)malloc((n + 1) * sizeof(char *));
    for (Py_ssize_t i = 0; i < n; i++)
    {
        arr[i] = PyUnicode_AsUTF8(PyList_GET_ITEM(list, i));
    }
    arr[n] = NULL;
    *out_count = (int)n;
    return arr;
}

static PyObject *extract_results(NSArray<VNRecognizedTextObservation *> *observations)
{
    PyObject *list = PyList_New(0);
    if (!observations)
    {
        return list;
    }

    for (VNRecognizedTextObservation *obs in observations)
    {
        VNRecognizedText *candidate = [[obs topCandidates:1] firstObject];
        if (!candidate || candidate.string.length == 0)
        {
            continue;
        }

        CGRect bbox = obs.boundingBox;
        PyObject *tup = Py_BuildValue("(sdddd)",
                                      candidate.string.UTF8String,
                                      bbox.origin.x,
                                      1.0 - (bbox.origin.y + bbox.size.height),
                                      bbox.size.width,
                                      bbox.size.height);
        PyList_Append(list, tup);
        Py_DECREF(tup);
    }
    return list;
}

static PyObject *run_request(
    VNImageRequestHandler *handler,
    double roi_x, double roi_y, double roi_w, double roi_h,
    int high_accuracy,
    const char **langs, int lang_count,
    const char **custom_words, int word_count)
{
    VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];

    request.recognitionLevel = high_accuracy
                                   ? VNRequestTextRecognitionLevelAccurate
                                   : VNRequestTextRecognitionLevelFast;

    request.regionOfInterest = CGRectMake(roi_x, 1.0 - roi_y - roi_h, roi_w, roi_h);

    if (lang_count > 0)
    {
        NSMutableArray<NSString *> *langArray = [NSMutableArray arrayWithCapacity:lang_count];
        for (int i = 0; i < lang_count; i++)
        {
            [langArray addObject:[NSString stringWithUTF8String:langs[i]]];
        }
        request.recognitionLanguages = langArray;
    }

    if (word_count > 0 && high_accuracy)
    {
        NSMutableArray<NSString *> *wordArray = [NSMutableArray arrayWithCapacity:word_count];
        for (int i = 0; i < word_count; i++)
        {
            [wordArray addObject:[NSString stringWithUTF8String:custom_words[i]]];
        }
        request.customWords = wordArray;
    }

    NSError *error = nil;
    if (![handler performRequests:@[request] error:&error])
    {
        return PyList_New(0);
    }

    return extract_results(request.results);
}

PyObject *py_get_supported_langs(PyObject *self, PyObject *args)
{
    VNRecognizeTextRequest *req = [[VNRecognizeTextRequest alloc] init];
    req.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
    NSError *error = nil;
    NSArray<NSString *> *langs = [req supportedRecognitionLanguagesAndReturnError:&error];

    if (error || !langs)
    {
        return PyList_New(0);
    }

    PyObject *list = PyList_New(langs.count);
    for (NSUInteger i = 0; i < langs.count; i++)
    {
        PyList_SET_ITEM(list, i, PyUnicode_FromString(langs[i].UTF8String));
    }
    return list;
}

PyObject *py_detect_bgra8(PyObject *self, PyObject *args)
{
    Py_buffer bgra8_buf;
    int width, height, high_accuracy;
    PyObject *roi_tuple, *langs_list, *custom_words_list;
    PyArg_ParseTuple(args, "y*iiOpOO",
                     &bgra8_buf, &width, &height,
                     &roi_tuple, &high_accuracy,
                     &langs_list, &custom_words_list);

    double roi_x = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 0));
    double roi_y = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 1));
    double roi_w = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 2));
    double roi_h = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 3));

    int lang_count = 0, word_count = 0;
    const char **langs = unpack_str_list(langs_list, &lang_count);
    const char **words = unpack_str_list(custom_words_list, &word_count);

    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    CGDataProviderRef provider = CGDataProviderCreateWithData(
        NULL, bgra8_buf.buf, (size_t)(width * height * 4), NULL);
    CGImageRef cgImage = CGImageCreate(
        (size_t)width, (size_t)height,
        8, 32, (size_t)(width * 4),
        colorSpace,
        kCGBitmapByteOrder32Little | kCGImageAlphaPremultipliedFirst,
        provider,
        NULL, false, kCGRenderingIntentDefault);
    CGColorSpaceRelease(colorSpace);
    CGDataProviderRelease(provider);

    PyObject *py_result;
    if (!cgImage)
    {
        py_result = PyList_New(0);
    }
    else
    {
        VNImageRequestHandler *handler = [[VNImageRequestHandler alloc]
            initWithCGImage:cgImage
                    options:@{}];
        CGImageRelease(cgImage);
        py_result = run_request(handler, roi_x, roi_y, roi_w, roi_h,
                                high_accuracy, langs, lang_count, words, word_count);
    }

    PyBuffer_Release(&bgra8_buf);
    free(langs);
    free(words);
    return py_result;
}

PyObject *py_detect_image(PyObject *self, PyObject *args)
{
    Py_buffer data_buf;
    int high_accuracy;
    PyObject *roi_tuple, *langs_list, *custom_words_list;
    PyArg_ParseTuple(args, "y*OpOO",
                     &data_buf,
                     &roi_tuple, &high_accuracy,
                     &langs_list, &custom_words_list);

    double roi_x = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 0));
    double roi_y = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 1));
    double roi_w = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 2));
    double roi_h = PyFloat_AsDouble(PyTuple_GET_ITEM(roi_tuple, 3));

    int lang_count = 0, word_count = 0;
    const char **langs = unpack_str_list(langs_list, &lang_count);
    const char **words = unpack_str_list(custom_words_list, &word_count);

    int img_width = 0, img_height = 0;
    PyObject *py_list;

    NSData *nsData = [NSData dataWithBytesNoCopy:(void *)data_buf.buf
                                          length:data_buf.len
                                    freeWhenDone:NO];
    CGImageSourceRef imageSource = CGImageSourceCreateWithData((__bridge CFDataRef)nsData, NULL);
    if (!imageSource)
    {
        py_list = PyList_New(0);
    }
    else
    {
        CGImageRef cgImage = CGImageSourceCreateImageAtIndex(imageSource, 0, NULL);
        CFRelease(imageSource);
        if (!cgImage)
        {
            py_list = PyList_New(0);
        }
        else
        {
            img_width = (int)CGImageGetWidth(cgImage);
            img_height = (int)CGImageGetHeight(cgImage);
            VNImageRequestHandler *handler = [[VNImageRequestHandler alloc]
                initWithCGImage:cgImage
                        options:@{}];
            CGImageRelease(cgImage);
            py_list = run_request(handler, roi_x, roi_y, roi_w, roi_h,
                                  high_accuracy, langs, lang_count, words, word_count);
        }
    }

    PyBuffer_Release(&data_buf);
    free(langs);
    free(words);
    return Py_BuildValue("(Nii)", py_list, img_width, img_height);
}
