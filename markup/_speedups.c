/*
 * Copyright (C) 2006 Edgewall Software
 * All rights reserved.
 *
 * This software is licensed as described in the file COPYING, which
 * you should have received as part of this distribution. The terms
 * are also available at http://markup.edgewall.org/wiki/License.
 *
 * This software consists of voluntary contributions made by many
 * individuals. For the exact contribution history, see the revision
 * history and logs, available at http://markup.edgewall.org/log/.
 */

#include <Python.h>

static PyObject *escape(PyObject *text, int quotes);

PyAPI_DATA(PyTypeObject) MarkupType;

PyDoc_STRVAR(Markup__doc__,
"Marks a string as being safe for inclusion in HTML/XML output without\n\
needing to be escaped.");

PyDoc_STRVAR(escape__doc__,
"Create a Markup instance from a string and escape special characters\n\
it may contain (<, >, & and \").\n\
\n\
If the `quotes` parameter is set to `False`, the \" character is left\n\
as is. Escaping quotes is generally only required for strings that are\n\
to be used in attribute values.");

PyDoc_STRVAR(unescape__doc__,
"Reverse-escapes &, <, > and \" and returns a `unicode` object.");

static PyObject *amp1, *amp2, *lt1, *lt2, *gt1, *gt2, *qt1, *qt2;

static void
init_constants(void)
{
    amp1 = PyUnicode_DecodeASCII("&", 1, NULL);
    amp2 = PyUnicode_DecodeASCII("&amp;", 5, NULL);
    lt1 = PyUnicode_DecodeASCII("<", 1, NULL);
    lt2 = PyUnicode_DecodeASCII("&lt;", 4, NULL);
    gt1 = PyUnicode_DecodeASCII(">", 1, NULL);
    gt2 = PyUnicode_DecodeASCII("&gt;", 4, NULL);
    qt1 = PyUnicode_DecodeASCII("\"", 1, NULL);
    qt2 = PyUnicode_DecodeASCII("&#34;", 5, NULL);
}

static PyObject *
Markup_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyObject *text, *tmp, *ret, *args2;
    int nargs, i;

    nargs = PyTuple_GET_SIZE(args);
    if (nargs == 0) {
        return PyUnicode_Type.tp_new(type, NULL, NULL);
    } else if (nargs == 1) {
        return PyUnicode_Type.tp_new(type, args, NULL);
    } else {
        text = PyTuple_GET_ITEM(args, 0);
        args2 = PyTuple_New(nargs - 1);
        if (args2 == NULL)
            return NULL;
        for (i = 1; i < nargs; i++) {
            tmp = escape(PyTuple_GET_ITEM(args, i), 1);
            if (tmp == NULL) {
                Py_DECREF(args2);
                return NULL;
            }
            PyTuple_SET_ITEM(args2, i - 1, tmp);
        }
        tmp = PyUnicode_Format(text, args2);
        Py_DECREF(args2);
        if (tmp == NULL)
            return NULL;
        args = PyTuple_New(1);
        if (args == NULL) {
            Py_DECREF(tmp);
            return NULL;
        }
        PyTuple_SET_ITEM(args, 0, tmp);
        ret = PyUnicode_Type.tp_new(type, args, NULL);
        Py_DECREF(args);
        return ret;
    }
}

static PyObject *
escape(PyObject *text, int quotes)
{
    PyObject *tmp, *tmp2, *args, *ret;

    tmp = PyUnicode_Replace(text, amp1, amp2, -1);
    tmp2 = PyUnicode_Replace(tmp, lt1, lt2, -1);
    Py_DECREF(tmp);
    tmp = PyUnicode_Replace(tmp2, gt1, gt2, -1);
    Py_DECREF(tmp2);
    if (quotes) {
        tmp2 = PyUnicode_Replace(tmp, qt1, qt2, -1);
        Py_DECREF(tmp);
        tmp = tmp2;
    }
    args = PyTuple_New(1);
    PyTuple_SET_ITEM(args, 0, tmp);
    ret = MarkupType.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return ret;
}

static PyObject *
Markup_escape(PyTypeObject* type, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"text", "quotes", 0};
    PyObject *text = NULL;
    char quotes = 1;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|b", kwlist, &text, &quotes)) {
        return NULL;
    }
    if (PyObject_Not(text)) {
        return type->tp_new(type, NULL, NULL);
    }
    if (PyObject_TypeCheck(text, type)) {
        Py_INCREF(text);
        return text;
    }
    return escape(text, quotes);
}

static PyObject *
Markup_mod(PyObject *self, PyObject *args)
{
    PyObject *tmp, *ret, *args2;
    int i, nargs;

    printf("1\n");
    nargs = PyTuple_GET_SIZE(args);
    args2 = PyTuple_New(nargs);
    if (args2 == NULL) {
        return NULL;
    }
    printf("2\n");
    for(i = 0; i < nargs; i++) {
        tmp = escape(PyTuple_GET_ITEM(args, i), 1);
        if (tmp == NULL) {
            Py_DECREF(args2);
            return NULL;
        }
        PyTuple_SET_ITEM(args2, i, tmp);
    }
    printf("3\n");
    tmp = PyUnicode_Format(self, args2);
    Py_DECREF(args2);
    if (tmp == NULL)
        return NULL;
    printf("4\n");
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF(tmp);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, tmp);
    ret = PyUnicode_Type.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return ret;
}

static PyObject *
Markup_unescape(PyObject* self)
{
    PyObject *tmp, *tmp2;

    tmp = PyUnicode_Replace(self, qt2, qt1, -1);
    if(tmp == NULL) return NULL;
    tmp2 = PyUnicode_Replace(tmp, gt2, gt1, -1);
    Py_DECREF(tmp);
    if(tmp2 == NULL) return NULL;
    tmp = PyUnicode_Replace(tmp2, lt2, lt1, -1);
    Py_DECREF(tmp2);
    if(tmp == NULL) return NULL;
    tmp2 = PyUnicode_Replace(tmp, amp2, amp1, -1);
    Py_DECREF(tmp);
    return tmp2;
}

typedef struct {
    PyUnicodeObject HEAD;
} MarkupObject;

static PyMethodDef Markup_methods[] = {
    {"escape", (PyCFunction)Markup_escape, METH_VARARGS|METH_CLASS|METH_KEYWORDS, 
     escape__doc__},
    {"unescape", (PyCFunction)Markup_unescape, METH_NOARGS, unescape__doc__},
    {NULL}  /* Sentinel */
};

static PyNumberMethods markup_as_number = {
        0,                              /*nb_add*/
        0,                              /*nb_subtract*/
        0,                              /*nb_multiply*/
        0,                              /*nb_divide*/
        Markup_mod,                     /*nb_remainder*/
};

PyTypeObject MarkupType = {
    PyObject_HEAD_INIT(NULL)
    0,
    "markup._speedups.Markup",
    sizeof(MarkupObject),
    0,
    0,          /*tp_dealloc*/
    0,          /*tp_print*/ 
    0,          /*tp_getattr*/
    0,          /*tp_setattr*/
    0,          /*tp_compare*/
    0,          /*tp_repr*/
    &markup_as_number,/*tp_as_number*/
    0,          /*tp_as_sequence*/
    0,          /*tp_as_mapping*/
    0,          /*tp_hash */

    0,          /*tp_call*/
    0,          /*tp_str*/
    0,          /*tp_getattro*/
    0,          /*tp_setattro*/
    0,          /*tp_as_buffer*/

    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    Markup__doc__,/*tp_doc*/
    
    0,          /*tp_traverse*/
    0,          /*tp_clear*/

    0,          /*tp_richcompare*/
    0,          /*tp_weaklistoffset*/

    0,          /*tp_iter*/
    0,          /*tp_iternext*/

    /* Attribute descriptor and subclassing stuff */

    Markup_methods,/*tp_methods*/
    0,          /*tp_members*/
    0,          /*tp_getset*/
    &PyUnicode_Type, /*tp_base*/
    0,          /*tp_dict*/
    
    0,          /*tp_descr_get*/
    0,          /*tp_descr_set*/
    0,          /*tp_dictoffset*/
    
    0,          /*tp_init*/
    0,          /*tp_alloc  will be set to PyType_GenericAlloc in module init*/
    Markup_new, /*tp_new*/
    0,          /*tp_free  Low-level free-memory routine */
    0,          /*tp_is_gc For PyObject_IS_GC */
    0,          /*tp_bases*/
    0,          /*tp_mro method resolution order */
    0,          /*tp_cache*/
    0,          /*tp_subclasses*/
    0           /*tp_weaklist*/
};

PyMODINIT_FUNC
init_speedups(void)
{
    PyObject *module;

    if (PyType_Ready(&MarkupType) < 0)
        return;

    init_constants();
    
    module = Py_InitModule("_speedups", NULL);
    Py_INCREF(&MarkupType);
    PyModule_AddObject(module, "Markup", (PyObject*)&MarkupType);
}
