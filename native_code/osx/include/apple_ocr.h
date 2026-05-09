#pragma once
#include <Python.h>

PyObject *py_get_supported_langs(PyObject *self, PyObject *args);
PyObject *py_detect_bgra8(PyObject *self, PyObject *args);
PyObject *py_detect_image(PyObject *self, PyObject *args);
