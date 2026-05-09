#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "apple_ocr.h"

static PyMethodDef methods[] = {
    {"get_supported_langs", py_get_supported_langs, METH_NOARGS, NULL},
    {"detect_bgra8", py_detect_bgra8, METH_VARARGS, NULL},
    {"detect_image", py_detect_image, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "_ocr_native", NULL, -1, methods};

PyMODINIT_FUNC PyInit__ocr_native(void)
{
    return PyModule_Create(&moduledef);
}
