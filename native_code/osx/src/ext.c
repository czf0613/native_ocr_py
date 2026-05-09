#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>
#include "apple_ocr.h"

static const char **unpack_str_list(PyObject *list, int *out_count) {
    Py_ssize_t n = PyList_GET_SIZE(list);
    const char **arr = (const char **)malloc((n + 1) * sizeof(char *));
    for (Py_ssize_t i = 0; i < n; i++) {
        arr[i] = PyUnicode_AsUTF8(PyList_GET_ITEM(list, i));
    }
    arr[n] = NULL;
    *out_count = (int)n;
    return arr;
}

static PyObject *results_to_pylist(OcrResultList result) {
    PyObject *list = PyList_New(result.count);
    for (int i = 0; i < result.count; i++) {
        OcrItem *it = &result.items[i];
        PyObject *tup = Py_BuildValue("(sdddd)", it->text, it->x, it->y, it->width, it->height);
        PyList_SET_ITEM(list, i, tup);
    }
    return list;
}

static PyObject *py_get_supported_langs(PyObject *self, PyObject *args) {
    char **langs = ocr_get_supported_langs();

    int count = 0;
    for (; langs[count]; count++) {}

    PyObject *list = PyList_New(count);
    for (int i = 0; i < count; i++) {
        PyList_SET_ITEM(list, i, PyUnicode_FromString(langs[i]));
    }

    ocr_langs_free(langs);
    return list;
}

static PyObject *py_detect_bgra8(PyObject *self, PyObject *args) {
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
    OcrResultList result = ocr_detect_image(
        (const uint8_t *)data_buf.buf, (size_t)data_buf.len,
        roi_x, roi_y, roi_w, roi_h,
        high_accuracy, langs, lang_count, words, word_count,
        &img_width, &img_height
    );

    PyBuffer_Release(&data_buf);
    free(langs);
    free(words);

    PyObject *py_list = results_to_pylist(result);
    ocr_result_free(result);
    return Py_BuildValue("(Nii)", py_list, img_width, img_height);
}

static PyMethodDef methods[] = {
    {"get_supported_langs", py_get_supported_langs, METH_NOARGS, NULL},
    {"detect_bgra8",        py_detect_bgra8,        METH_VARARGS, NULL},
    {"detect_image",        py_detect_image,        METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "_ocr_native", NULL, -1, methods
};

PyMODINIT_FUNC PyInit__ocr_native(void) {
    return PyModule_Create(&moduledef);
}
