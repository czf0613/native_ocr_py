#define PY_SSIZE_T_CLEAN
#import <Python.h>
#import <Vision/Vision.h>
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>
#include <math.h>
#include <string.h>

static void set_native_error(const char *operation, NSError *error)
{
    PyErr_Format(PyExc_RuntimeError, "%s failed (%s, code %ld)", operation,
                 error.domain.UTF8String ?: "no error details", (long)error.code);
}

static void set_objc_error(NSException *exception)
{
    PyErr_Format(PyExc_RuntimeError, "Vision bridge raised %s",
                 exception.name.UTF8String ?: "an Objective-C exception");
}

static int parse_roi(PyObject *roi, double values[4])
{
    if (!PyTuple_Check(roi) || PyTuple_GET_SIZE(roi) != 4)
    {
        PyErr_SetString(PyExc_TypeError, "roi must be a tuple of four numbers");
        return 0;
    }
    for (Py_ssize_t i = 0; i < 4; i++)
    {
        values[i] = PyFloat_AsDouble(PyTuple_GET_ITEM(roi, i));
        if (PyErr_Occurred())
        {
            return 0;
        }
        if (!isfinite(values[i]))
        {
            PyErr_SetString(PyExc_ValueError, "roi values must be finite");
            return 0;
        }
    }
    if (values[0] < 0 || values[1] < 0 || values[2] <= 0 || values[3] <= 0 ||
        values[0] + values[2] > 1 || values[1] + values[3] > 1)
    {
        PyErr_SetString(PyExc_ValueError, "roi must have positive size and lie within [0, 1]");
        return 0;
    }
    return 1;
}

static NSArray<NSString *> *unpack_str_list(PyObject *list, const char *name)
{
    if (!PyList_Check(list))
    {
        PyErr_Format(PyExc_TypeError, "%s must be a list of strings", name);
        return nil;
    }
    Py_ssize_t count = PyList_GET_SIZE(list);
    NSMutableArray<NSString *> *array = [NSMutableArray arrayWithCapacity:(NSUInteger)count];
    if (!array)
    {
        PyErr_NoMemory();
        return nil;
    }
    for (Py_ssize_t i = 0; i < count; i++)
    {
        PyObject *item = PyList_GET_ITEM(list, i);
        if (!PyUnicode_Check(item))
        {
            PyErr_Format(PyExc_TypeError, "%s entries must be strings", name);
            return nil;
        }
        Py_ssize_t length;
        const char *utf8 = PyUnicode_AsUTF8AndSize(item, &length);
        if (!utf8)
        {
            return nil;
        }
        if (memchr(utf8, '\0', (size_t)length))
        {
            PyErr_Format(PyExc_ValueError, "%s entries must not contain NUL", name);
            return nil;
        }
        NSString *string = [[NSString alloc] initWithBytes:utf8
                                                   length:(NSUInteger)length
                                                 encoding:NSUTF8StringEncoding];
        if (!string)
        {
            PyErr_NoMemory();
            return nil;
        }
        [array addObject:string];
    }
    // Foundation strings own their data before any GIL release or list mutation.
    return array;
}

static PyObject *python_string(NSString *string)
{
    const char *utf8 = string.UTF8String;
    NSUInteger length = [string lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
    if (!utf8)
    {
        PyErr_SetString(PyExc_RuntimeError, "Vision returned invalid text");
        return NULL;
    }
    if (length > PY_SSIZE_T_MAX)
    {
        PyErr_SetString(PyExc_OverflowError, "Vision text is too large");
        return NULL;
    }
    return PyUnicode_DecodeUTF8(utf8, (Py_ssize_t)length, "strict");
}

static PyObject *extract_results(NSArray<VNRecognizedTextObservation *> *observations,
                                 const double roi[4])
{
    PyObject *list = PyList_New(0);
    if (!list)
    {
        return NULL;
    }
    @try
    {
        for (VNRecognizedTextObservation *obs in observations)
        {
            VNRecognizedText *candidate = [[obs topCandidates:1] firstObject];
            if (!candidate || candidate.string.length == 0)
            {
                continue;
            }
            CGRect bbox = obs.boundingBox;
            PyObject *text = python_string(candidate.string);
            if (!text)
            {
                Py_DECREF(list);
                return NULL;
            }
            // Vision reports coordinates in the processed ROI. Public results
            // use the entire source image, in top-left-origin coordinates.
            PyObject *tuple = Py_BuildValue("(Odddd)", text,
                                            roi[0] + bbox.origin.x * roi[2],
                                            roi[1] + (1.0 - (bbox.origin.y + bbox.size.height)) * roi[3],
                                            bbox.size.width * roi[2], bbox.size.height * roi[3]);
            Py_DECREF(text);
            if (!tuple)
            {
                Py_DECREF(list);
                return NULL;
            }
            int status = PyList_Append(list, tuple);
            Py_DECREF(tuple);
            if (status < 0)
            {
                Py_DECREF(list);
                return NULL;
            }
        }
    }
    @catch (NSException *exception)
    {
        Py_DECREF(list);
        @throw;
    }
    return list;
}

static PyObject *run_request(VNImageRequestHandler *handler, const double roi[4],
                             int high_accuracy, NSArray<NSString *> *langs,
                             NSArray<NSString *> *words)
{
    VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
    if (!handler || !request)
    {
        return PyErr_NoMemory();
    }
    request.recognitionLevel = high_accuracy ? VNRequestTextRecognitionLevelAccurate
                                            : VNRequestTextRecognitionLevelFast;
    // Sum first: (1 - y) - height can be negative for a valid bottom-edge ROI.
    request.regionOfInterest = CGRectMake(roi[0], 1.0 - (roi[1] + roi[3]), roi[2], roi[3]);
    if (langs.count > 0)
    {
        request.recognitionLanguages = langs;
    }
    if (words.count > 0 && high_accuracy)
    {
        request.customWords = words;
    }
    NSArray<VNRequest *> *requests = @[request];
    NSError *error = nil;
    BOOL success = NO;
    // Only Vision runs without the GIL. All inputs are owned native snapshots.
    // @finally restores the GIL even if Vision raises an Objective-C exception.
    PyThreadState *thread_state = PyEval_SaveThread();
    @try
    {
        success = [handler performRequests:requests error:&error];
    }
    @finally
    {
        PyEval_RestoreThread(thread_state);
    }
    if (!success || error)
    {
        set_native_error("Vision text recognition", error);
        return NULL;
    }
    return extract_results(request.results, roi);
}

PyObject *py_get_supported_langs(PyObject *self, PyObject *args)
{
    @autoreleasepool
    {
        PyObject *list = NULL;
        @try
        {
            VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
            if (!request)
            {
                return PyErr_NoMemory();
            }
            request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
            NSError *error = nil;
            NSArray<NSString *> *langs = [request supportedRecognitionLanguagesAndReturnError:&error];
            if (error || !langs)
            {
                set_native_error("Vision language query", error);
                return NULL;
            }
            list = PyList_New(0);
            if (!list)
            {
                return NULL;
            }
            for (NSString *lang in langs)
            {
                PyObject *text = python_string(lang);
                if (!text)
                {
                    Py_DECREF(list);
                    return NULL;
                }
                int status = PyList_Append(list, text);
                Py_DECREF(text);
                if (status < 0)
                {
                    Py_DECREF(list);
                    return NULL;
                }
            }
        }
        @catch (NSException *exception)
        {
            Py_XDECREF(list);
            set_objc_error(exception);
            return NULL;
        }
        return list;
    }
}

static PyObject *detect_buffer(Py_buffer *buffer, int width, int height, PyObject *roi_object,
                               int high_accuracy, PyObject *langs_object,
                               PyObject *words_object, int is_bgra)
{
    double roi[4];
    if (!parse_roi(roi_object, roi))
    {
        return NULL;
    }
    NSArray<NSString *> *langs = unpack_str_list(langs_object, "languages");
    if (!langs)
    {
        return NULL;
    }
    NSArray<NSString *> *words = unpack_str_list(words_object, "custom_words");
    if (!words)
    {
        return NULL;
    }
    size_t row_bytes = 0;
    if (is_bgra)
    {
        if (width <= 0 || height <= 0)
        {
            PyErr_SetString(PyExc_ValueError, "BGRA width and height must be positive");
            return NULL;
        }
        if ((size_t)width > (size_t)PY_SSIZE_T_MAX / 4)
        {
            PyErr_SetString(PyExc_OverflowError, "BGRA row size is not representable");
            return NULL;
        }
        row_bytes = (size_t)width * 4;
        if ((size_t)height > (size_t)PY_SSIZE_T_MAX / row_bytes)
        {
            PyErr_SetString(PyExc_OverflowError, "BGRA buffer size is not representable");
            return NULL;
        }
        if ((size_t)buffer->len != row_bytes * (size_t)height)
        {
            PyErr_SetString(PyExc_ValueError, "BGRA buffer length must equal width * height * 4");
            return NULL;
        }
    }

    // Always copy, including readonly views of mutable exporters. A buffer export
    // prevents resizing, but does not prevent another thread from writing to it.
    NSData *snapshot = [[NSData alloc] initWithBytes:buffer->buf length:(NSUInteger)buffer->len];
    if (!snapshot)
    {
        return PyErr_NoMemory();
    }
    CGColorSpaceRef color_space = NULL;
    CGDataProviderRef provider = NULL;
    CGImageSourceRef source = NULL;
    CGImageRef image = NULL;
    @try
    {
        if (is_bgra)
        {
            color_space = CGColorSpaceCreateDeviceRGB();
            if (!color_space)
            {
                return PyErr_NoMemory();
            }
            provider = CGDataProviderCreateWithCFData((__bridge CFDataRef)snapshot);
            if (!provider)
            {
                return PyErr_NoMemory();
            }
            image = CGImageCreate((size_t)width, (size_t)height, 8, 32, row_bytes,
                                  color_space,
                                  kCGBitmapByteOrder32Little | kCGImageAlphaPremultipliedFirst,
                                  provider, NULL, false, kCGRenderingIntentDefault);
            if (!image)
            {
                PyErr_SetString(PyExc_RuntimeError, "CoreGraphics could not create the BGRA image");
                return NULL;
            }
        }
        else
        {
            source = CGImageSourceCreateWithData((__bridge CFDataRef)snapshot, NULL);
            if (source)
            {
                image = CGImageSourceCreateImageAtIndex(source, 0, NULL);
            }
            if (!image)
            {
                PyErr_SetString(PyExc_ValueError, "ImageIO could not decode the image data");
                return NULL;
            }
        }
        size_t image_width = CGImageGetWidth(image);
        size_t image_height = CGImageGetHeight(image);
        if (image_width > PY_SSIZE_T_MAX || image_height > PY_SSIZE_T_MAX)
        {
            PyErr_SetString(PyExc_OverflowError, "decoded image dimensions are not representable");
            return NULL;
        }
        VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithCGImage:image options:@{}];
        PyObject *results = run_request(handler, roi, high_accuracy, langs, words);
        if (!results || is_bgra)
        {
            return results;
        }
        return Py_BuildValue("(Nnn)", results, (Py_ssize_t)image_width, (Py_ssize_t)image_height);
    }
    @finally
    {
        if (image)
        {
            CGImageRelease(image);
        }
        if (source)
        {
            CFRelease(source);
        }
        if (provider)
        {
            CGDataProviderRelease(provider);
        }
        if (color_space)
        {
            CGColorSpaceRelease(color_space);
        }
    }
}

static PyObject *detect(PyObject *args, int is_bgra)
{
    Py_buffer buffer = {0};
    int width = 0, height = 0, high_accuracy;
    PyObject *roi, *langs, *words;
    if (is_bgra)
    {
        if (!PyArg_ParseTuple(args, "y*iiOpOO:detect_bgra8", &buffer, &width, &height,
                              &roi, &high_accuracy, &langs, &words))
        {
            return NULL;
        }
    }
    else if (!PyArg_ParseTuple(args, "y*OpOO:detect_image", &buffer, &roi,
                               &high_accuracy, &langs, &words))
    {
        return NULL;
    }
    PyObject *result = NULL;
    @autoreleasepool
    {
        @try
        {
            result = detect_buffer(&buffer, width, height, roi, high_accuracy, langs, words, is_bgra);
        }
        @catch (NSException *exception)
        {
            set_objc_error(exception);
        }
        @finally
        {
            PyBuffer_Release(&buffer);
        }
    }
    return result;
}

PyObject *py_detect_bgra8(PyObject *self, PyObject *args)
{
    return detect(args, 1);
}

PyObject *py_detect_image(PyObject *self, PyObject *args)
{
    return detect(args, 0);
}
