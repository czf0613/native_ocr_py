#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>
#include "apple_ocr.h"

/* ---- Helpers -------------------------------------------------- */

/*
 * Convert a Python list[str] into a heap-allocated const char** array.
 * The strings themselves point into Python's internal UTF-8 buffer and
 * must NOT be freed individually — only the array itself should be freed.
 * The Python list must remain alive for the lifetime of the returned array.
 * Returns NULL and sets a Python exception on error.
 */
static const char **parse_str_list(PyObject *list, int *out_count) {
    if (!PyList_Check(list)) {
        PyErr_SetString(PyExc_TypeError, "expected a list of strings");
        return NULL;
    }
    Py_ssize_t n = PyList_GET_SIZE(list);
    const char **arr = (const char **)malloc((n + 1) * sizeof(char *));
    if (!arr) { PyErr_NoMemory(); return NULL; }
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *item = PyList_GET_ITEM(list, i);
        if (!PyUnicode_Check(item)) {
            free(arr);
            PyErr_SetString(PyExc_TypeError, "list elements must be strings");
            return NULL;
        }
        arr[i] = PyUnicode_AsUTF8(item);
        if (!arr[i]) { free(arr); return NULL; }
    }
    arr[n] = NULL;
    *out_count = (int)n;
    return arr;
}

/*
 * Convert an OcrResultList to list[tuple[str, float, float, float, float]].
 * Each tuple is (text, x, y, width, height).
 */
static PyObject *results_to_pylist(OcrResultList result) {
    PyObject *list = PyList_New(result.count);
    if (!list) return NULL;
    for (int i = 0; i < result.count; i++) {
        OcrItem *it = &result.items[i];
        PyObject *tup = Py_BuildValue("(sdddd)", it->text, it->x, it->y, it->width, it->height);
        if (!tup) { Py_DECREF(list); return NULL; }
        PyList_SET_ITEM(list, i, tup);  /* steals reference */
    }
    return list;
}

/* ---- Module functions ----------------------------------------- */

static PyObject *py_get_supported_langs(PyObject *self, PyObject *args) {
    char **langs = ocr_get_supported_langs();

    PyObject *list = PyList_New(0);
    if (!list) { ocr_langs_free(langs); return NULL; }

    for (int i = 0; langs[i]; i++) {
        PyObject *s = PyUnicode_FromString(langs[i]);
        if (!s || PyList_Append(list, s) < 0) {
            Py_XDECREF(s);
            Py_DECREF(list);
            ocr_langs_free(langs);
            return NULL;
        }
        Py_DECREF(s);
    }

    ocr_langs_free(langs);
    return list;
}

static PyObject *py_detect_bgra8(PyObject *self, PyObject *args) {
    Py_buffer  bgra8_buf;
    int        width, height, high_accuracy;
    PyObject  *roi_tuple, *langs_list, *custom_words_list;

    if (!PyArg_ParseTuple(args, "y*iiOpOO",
            &bgra8_buf, &width, &height,
            &roi_tuple, &high_accuracy,
            &langs_list, &custom_words_list)) {
        return NULL;
    }

    double roi_x, roi_y, roi_w, roi_h;
    if (!PyArg_ParseTuple(roi_tuple, "dddd", &roi_x, &roi_y, &roi_w, &roi_h)) {
        PyBuffer_Release(&bgra8_buf);
        return NULL;
    }

    int lang_count = 0, word_count = 0;
    const char **langs = parse_str_list(langs_list, &lang_count);
    if (!langs) { PyBuffer_Release(&bgra8_buf); return NULL; }
    const char **words = parse_str_list(custom_words_list, &word_count);
    if (!words) { free(langs); PyBuffer_Release(&bgra8_buf); return NULL; }

    OcrResultList result = ocr_detect_bgra8(
        (const uint8_t *)bgra8_buf.buf, width, height,
        roi_x, roi_y, roi_w, roi_h,
        high_accuracy, langs, lang_count, words, word_count
    );

    PyBuffer_Release(&bgra8_buf);
    free(langs);
    free(words);

    PyObject *py_result = results_to_pylist(result);
    ocr_result_free(result);
    return py_result;
}

static PyObject *py_detect_image(PyObject *self, PyObject *args) {
    Py_buffer  data_buf;
    int        high_accuracy;
    PyObject  *roi_tuple, *langs_list, *custom_words_list;

    if (!PyArg_ParseTuple(args, "y*OpOO",
            &data_buf,
            &roi_tuple, &high_accuracy,
            &langs_list, &custom_words_list)) {
        return NULL;
    }

    double roi_x, roi_y, roi_w, roi_h;
    if (!PyArg_ParseTuple(roi_tuple, "dddd", &roi_x, &roi_y, &roi_w, &roi_h)) {
        PyBuffer_Release(&data_buf);
        return NULL;
    }

    int lang_count = 0, word_count = 0;
    const char **langs = parse_str_list(langs_list, &lang_count);
    if (!langs) { PyBuffer_Release(&data_buf); return NULL; }
    const char **words = parse_str_list(custom_words_list, &word_count);
    if (!words) { free(langs); PyBuffer_Release(&data_buf); return NULL; }

    OcrResultList result = ocr_detect_image(
        (const uint8_t *)data_buf.buf, (size_t)data_buf.len,
        roi_x, roi_y, roi_w, roi_h,
        high_accuracy, langs, lang_count, words, word_count
    );

    PyBuffer_Release(&data_buf);
    free(langs);
    free(words);

    PyObject *py_result = results_to_pylist(result);
    ocr_result_free(result);
    return py_result;
}

/* ---- Module definition --------------------------------------- */

static PyMethodDef methods[] = {
    {"get_supported_langs", py_get_supported_langs, METH_NOARGS,
     "Return BCP-47 language codes supported by the Vision OCR engine."},
    {"detect_bgra8",        py_detect_bgra8,        METH_VARARGS,
     "Run OCR on a raw BGRA8 pixel buffer."},
    {"detect_image",        py_detect_image,        METH_VARARGS,
     "Run OCR on an encoded image (JPEG, PNG, HEIC, ...)."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "_ocr_native", NULL, -1, methods
};

PyMODINIT_FUNC PyInit__ocr_native(void) {
    return PyModule_Create(&moduledef);
}
