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
#include <structmember.h>

/* Markup class */

static PyObject *escape(PyObject *text, int quotes);

PyAPI_DATA(PyTypeObject) MarkupType;

PyDoc_STRVAR(Markup__doc__,
"Marks a string as being safe for inclusion in HTML/XML output without\n\
needing to be escaped.");

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
    PyObject *self, *text, *tmp, *args2;
    int nargs, i;

    nargs = PyTuple_GET_SIZE(args);
    if (nargs == 0) {
        return PyUnicode_Type.tp_new(type, args, NULL);
    } else if (nargs == 1) {
        return PyUnicode_Type.tp_new(type, args, NULL);
    } else {
        text = PyTuple_GET_ITEM(args, 0);
        args2 = PyTuple_New(nargs - 1);
        if (args2 == NULL) {
            return NULL;
        }
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
        if (tmp == NULL) {
            return NULL;
        }
        args = PyTuple_New(1);
        if (args == NULL) {
            Py_DECREF(tmp);
            return NULL;
        }
        PyTuple_SET_ITEM(args, 0, tmp);
        self = PyUnicode_Type.tp_new(type, args, NULL);
        Py_DECREF(args);
        return self;
    }
}

static PyObject *
escape(PyObject *text, int quotes)
{
    PyObject *args, *ret;
    PyUnicodeObject *in, *out;
    Py_UNICODE *outp;
    int i, len;

    if (PyObject_TypeCheck(text, &MarkupType)) {
        Py_INCREF(text);
        return text;
    }
    in = (PyUnicodeObject *) PyObject_Unicode(text);
    if (in == NULL) {
        return NULL;
    }
    /* First we need to figure out how long the escaped string will be */
    len = 0;
    for (i = 0;i < in->length; i++) {
        switch (in->str[i]) {
            case '&': len += 5;                 break;
            case '"': len += quotes ? 5 : 1;    break;
            case '<':
            case '>': len += 4;                 break;
            default:  len++;
        }
    }
    /* Do we need to escape anything at all? */
    if (len == in->length) {
        args = PyTuple_New(1);
        if (args == NULL) {
            Py_DECREF((PyObject *) in);
            return NULL;
        }
        PyTuple_SET_ITEM(args, 0, (PyObject *) in);
        ret = MarkupType.tp_new(&MarkupType, args, NULL);
        Py_DECREF(args);
        return ret;
    }
    out = (PyUnicodeObject*) PyUnicode_FromUnicode(NULL, len);
    if (out == NULL) {
        return NULL;
    }
    outp = out->str;
    for (i = 0;i < in->length; i++) {
        switch (in->str[i]) {
        case '&':
            Py_UNICODE_COPY(outp, ((PyUnicodeObject *) amp2)->str, 5);
            outp += 5;
            break;
        case '"':
            if (quotes) {
                Py_UNICODE_COPY(outp, ((PyUnicodeObject *) qt2)->str, 5);
                outp += 5;
            } else {
                *outp++ = in->str[i];
            }
            break;
        case '<':
            Py_UNICODE_COPY(outp, ((PyUnicodeObject *) lt2)->str, 4);
            outp += 4;
            break;
        case '>':
            Py_UNICODE_COPY(outp, ((PyUnicodeObject *) gt2)->str, 4);
            outp += 4;
            break;
        default:
            *outp++ = in->str[i];
        };
    }
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF((PyObject *) out);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, (PyObject *) out);
    ret = MarkupType.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return ret;
}

PyDoc_STRVAR(escape__doc__,
"Create a Markup instance from a string and escape special characters\n\
it may contain (<, >, & and \").\n\
\n\
If the `quotes` parameter is set to `False`, the \" character is left\n\
as is. Escaping quotes is generally only required for strings that are\n\
to be used in attribute values.");

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
        return type->tp_new(type, args, NULL);
    }
    if (PyObject_TypeCheck(text, type)) {
        Py_INCREF(text);
        return text;
    }
    return escape(text, quotes);
}

static PyObject *
Markup_join(PyObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"seq", "escape_quotes", 0};
    PyObject *seq = NULL, *seq2, *tmp;
    char quotes = 1;
    int n, i;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|b", kwlist, &seq, &quotes)) {
        return NULL;
    }
    if (!PySequence_Check(seq)) {
        return NULL;
    }
    n = PySequence_Size(seq);
    if (n < 0) {
        return NULL;
    }
    seq2 = PyTuple_New(n);
    if (seq2 == NULL) {
        return NULL;
    }
    for (i = 0; i < n; i++) {
        tmp = PySequence_GetItem(seq, i);
        if (tmp == NULL) {
            Py_DECREF(seq2);
            return NULL;
        }
        tmp = escape(tmp, quotes);
        if (tmp == NULL) {
            Py_DECREF(seq2);
            return NULL;
        }
        PyTuple_SET_ITEM(seq2, i, tmp);
    }
    tmp = PyUnicode_Join(self, seq2);
    Py_DECREF(seq2);
    if (tmp == NULL)
        return NULL;
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF(tmp);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, tmp);
    tmp = MarkupType.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return tmp;
}

static PyObject *
Markup_concat(PyObject *self, PyObject *other)
{
    PyObject *tmp, *tmp2, *args, *ret;
    tmp = escape(other, 1);
    if (tmp == NULL)
        return NULL;
    tmp2 = PyUnicode_Concat(self, tmp);
    if (tmp2 == NULL) {
        Py_DECREF(tmp);
        return NULL;
    }
    Py_DECREF(tmp);
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF(tmp2);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, tmp2);
    ret = MarkupType.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return ret;
}

static PyObject *
Markup_mod(PyObject *self, PyObject *args)
{
    PyObject *tmp, *tmp2, *ret, *args2;
    int i, nargs;

    if (PyTuple_Check(args)) {
        nargs = PyTuple_GET_SIZE(args);
        args2 = PyTuple_New(nargs);
        if (args2 == NULL) {
            return NULL;
        }
        for (i = 0; i < nargs; i++) {
            tmp = escape(PyTuple_GET_ITEM(args, i), 1);
            if (tmp == NULL) {
                Py_DECREF(args2);
                return NULL;
            }
            PyTuple_SET_ITEM(args2, i, tmp);
        }
        tmp = PyUnicode_Format(self, args2);
        Py_DECREF(args2);
        if (tmp == NULL) {
            return NULL;
        }
    } else {
        tmp2 = escape(args, 1);
        if (tmp2 == NULL) {
            return NULL;
        }
        tmp = PyUnicode_Format(self, tmp2);
        Py_DECREF(tmp2);
        if (tmp == NULL) {
            return NULL;
        }
    }
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
Markup_mul(PyObject *self, PyObject *num)
{
    PyObject *unicode, *result, *args;

    unicode = PyObject_Unicode(self);
    if (unicode == NULL) return NULL;
    result = PyNumber_Multiply(unicode, num);
    if (result == NULL) return NULL;
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF(result);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, result);
    result = PyUnicode_Type.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return result;
}

static PyObject *
Markup_repr(PyObject *self)
{
    PyObject *format, *result, *args;

    format = PyString_FromString("<Markup \"%s\">");
    if (format == NULL) return NULL;
    result = PyObject_Unicode(self);
    if (result == NULL) return NULL;
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF(result);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, result);
    result = PyString_Format(format, args);
    Py_DECREF(args);
    return result;
}

PyDoc_STRVAR(unescape__doc__,
"Reverse-escapes &, <, > and \" and returns a `unicode` object.");

static PyObject *
Markup_unescape(PyObject* self)
{
    PyObject *tmp, *tmp2;

    tmp = PyUnicode_Replace(self, qt2, qt1, -1);
    if (tmp == NULL) return NULL;
    tmp2 = PyUnicode_Replace(tmp, gt2, gt1, -1);
    Py_DECREF(tmp);
    if (tmp2 == NULL) return NULL;
    tmp = PyUnicode_Replace(tmp2, lt2, lt1, -1);
    Py_DECREF(tmp2);
    if (tmp == NULL) return NULL;
    tmp2 = PyUnicode_Replace(tmp, amp2, amp1, -1);
    Py_DECREF(tmp);
    return tmp2;
}

PyDoc_STRVAR(stripentities__doc__,
"Return a copy of the text with any character or numeric entities\n\
replaced by the equivalent UTF-8 characters.\n\
\n\
If the `keepxmlentities` parameter is provided and evaluates to `True`,\n\
the core XML entities (&amp;, &apos;, &gt;, &lt; and &quot;) are not\n\
stripped.");

static PyObject *
Markup_stripentities(PyObject* self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"keepxmlentities", 0};
    PyObject *module, *func, *result, *args2;
    char keepxml = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|b", kwlist, &keepxml)) {
        return NULL;
    }

    module = PyImport_ImportModule("markup.core");
    if (module == NULL) return NULL;
    func = PyObject_GetAttrString(module, "stripentities");
    Py_DECREF(module);
    if (func == NULL) return NULL;
    result = PyObject_CallFunction(func, "Ob", self, keepxml);
    Py_DECREF(func);
    if (result == NULL) return NULL;
    args2 = PyTuple_New(1);
    if (args2 == NULL) {
        Py_DECREF(result);
        return NULL;
    }
    PyTuple_SET_ITEM(args2, 0, result);
    result = MarkupType.tp_new(&MarkupType, args2, NULL);
    Py_DECREF(args2);
    return result;
}

PyDoc_STRVAR(striptags__doc__,
"Return a copy of the text with all XML/HTML tags removed.");

static PyObject *
Markup_striptags(PyObject* self)
{
    PyObject *module, *func, *result, *args;

    module = PyImport_ImportModule("markup.core");
    if (module == NULL) return NULL;
    func = PyObject_GetAttrString(module, "striptags");
    Py_DECREF(module);
    if (func == NULL) return NULL;
    result = PyObject_CallFunction(func, "O", self);
    Py_DECREF(func);
    if (result == NULL) return NULL;
    args = PyTuple_New(1);
    if (args == NULL) {
        Py_DECREF(result);
        return NULL;
    }
    PyTuple_SET_ITEM(args, 0, result);
    result = MarkupType.tp_new(&MarkupType, args, NULL);
    Py_DECREF(args);
    return result;
}

typedef struct {
    PyUnicodeObject HEAD;
} MarkupObject;

static PyMethodDef Markup_methods[] = {
    {"escape", (PyCFunction) Markup_escape,
     METH_VARARGS|METH_CLASS|METH_KEYWORDS,  escape__doc__},
    {"join", (PyCFunction)Markup_join, METH_VARARGS|METH_KEYWORDS},
    {"unescape", (PyCFunction)Markup_unescape, METH_NOARGS, unescape__doc__},
    {"stripentities", (PyCFunction) Markup_stripentities,
     METH_VARARGS|METH_KEYWORDS, stripentities__doc__},
    {"striptags", (PyCFunction) Markup_striptags, METH_NOARGS,
     striptags__doc__},
    {NULL}  /* Sentinel */
};

static PyNumberMethods markup_as_number = {
        0, /*nb_add*/
        0, /*nb_subtract*/
        Markup_mul, /*nb_multiply*/
        0, /*nb_divide*/
        Markup_mod, /*nb_remainder*/
};

static PySequenceMethods markup_as_sequence = {
        0, /*sq_length*/
        Markup_concat, /*sq_concat*/
        0, /*sq_repeat*/
        0, /*sq_item*/
        0, /*sq_slice*/
        0, /*sq_ass_item*/
        0, /*sq_ass_slice*/
        0  /*sq_contains*/
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
    Markup_repr, /*tp_repr*/
    &markup_as_number, /*tp_as_number*/
    &markup_as_sequence, /*tp_as_sequence*/
    0,          /*tp_as_mapping*/
    0,          /*tp_hash */

    0,          /*tp_call*/
    0,          /*tp_str*/
    0,          /*tp_getattro*/
    0,          /*tp_setattro*/
    0,          /*tp_as_buffer*/

    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_CHECKTYPES, /*tp_flags*/
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

/* _ensure generator */

PyAPI_DATA(PyTypeObject) _ensureType;

typedef struct {
    PyObject_HEAD;
    PyObject *stream;
} _ensure;

static void
_ensure_dealloc(_ensure *self)
{
    Py_XDECREF(self->stream);
    self->ob_type->tp_free((PyObject *) self);
}

static int
_ensure_init(_ensure *self, PyObject *args, PyObject *kwds)
{
    PyObject *stream;
    if (!PyArg_ParseTuple(args, "O", &stream)) return -1;

    stream = PyObject_GetIter(stream);
    if (stream == NULL) return -1;
    Py_INCREF(stream);
    self->stream = stream;

    return 0;
}

static PyObject *
_ensure_iter(_ensure *self)
{
    Py_INCREF(self);
    return (PyObject *) self;
}

static PyObject *
_ensure_next(_ensure *self)
{
    PyObject *result, *tmp;

    result = PyIter_Next(self->stream);
    if (result == NULL) return NULL;
    Py_INCREF(result);

    if (!PyTuple_CheckExact(result)) {
        tmp = PyObject_CallMethod(result, "totuple", NULL);
        Py_DECREF(result);
        if (tmp == NULL) return NULL;
        Py_INCREF(tmp);
        return tmp;
    }

    return result;
}

PyTypeObject _ensureType = {
    PyObject_HEAD_INIT(NULL)
    0,          /*ob_size*/
    "markup._speedups._ensure", /*tp_name*/
    sizeof(_ensure),/*tp_basicsize*/
    0,          /*tp_itemsize*/
    (destructor) _ensure_dealloc, /*tp_dealloc*/
    0,          /*tp_print*/ 
    0,          /*tp_getattr*/
    0,          /*tp_setattr*/
    0,          /*tp_compare*/
    0,          /*tp_repr*/
    0,          /*tp_as_number*/
    0,          /*tp_as_sequence*/
    0,          /*tp_as_mapping*/
    0,          /*tp_hash */

    0,          /*tp_call*/
    0,          /*tp_str*/
    0,          /*tp_getattro*/
    0,          /*tp_setattro*/
    0,          /*tp_as_buffer*/

    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_ITER, /*tp_flags*/
    0,          /*tp_doc*/

    0,          /*tp_traverse*/
    0,          /*tp_clear*/

    0,          /*tp_richcompare*/
    0,          /*tp_weaklistoffset*/

    (getiterfunc) _ensure_iter, /*tp_iter*/
    (iternextfunc) _ensure_next, /*tp_iternext*/

    /* Attribute descriptor and subclassing stuff */

    0,          /*tp_methods*/
    0,          /*tp_members*/
    0,          /*tp_getset*/
    0,          /*tp_base*/
    0,          /*tp_dict*/

    0,          /*tp_descr_get*/
    0,          /*tp_descr_set*/
    0,          /*tp_dictoffset*/

    (initproc) _ensure_init, /*tp_init*/
    0,          /*tp_alloc  will be set to PyType_GenericAlloc in module init*/
    PyType_GenericNew          /*tp_new*/
};

/* _PushbackIterator class */

PyAPI_DATA(PyTypeObject) _PushbackIteratorType;

PyDoc_STRVAR(_PushbackIterator__doc__,
"A simple wrapper for iterators that allows pushing items back on the\n\
queue via the `pushback()` method.\n\
\n\
That can effectively be used to peek at the next item.");

typedef struct {
    PyObject_HEAD;
    PyObject *iterable;
    PyListObject *buf;
} _PushbackIterator;

static void
_PushbackIterator_dealloc(_PushbackIterator *self)
{
    Py_XDECREF(self->iterable);
    Py_XDECREF(self->buf);
    self->ob_type->tp_free((PyObject *) self);
}

static int
_PushbackIterator_init(_PushbackIterator *self, PyObject *args, PyObject *kwds)
{
    PyObject *iterable, *buf;
    if (!PyArg_ParseTuple(args, "O", &iterable)) return -1;

    iterable = PyObject_GetIter(iterable);
    if (iterable == NULL) return -1;
    Py_INCREF(iterable);

    buf = PyList_New(0);
    if (buf == NULL) {
        Py_DECREF(iterable);
        return -1;
    }
    Py_INCREF(buf);
    self->buf = (PyListObject *) buf;
    self->iterable = iterable;

    return 0;
}

static PyObject *
_PushbackIterator_iter(_PushbackIterator *self)
{
    Py_INCREF(self);
    return (PyObject *) self;
}

static PyObject *
_PushbackIterator_next(_PushbackIterator *self)
{
    PyObject *next;

    if (PyList_GET_SIZE(self->buf)) {
        next = PyList_GET_ITEM(self->buf, 0);
        if (next == NULL) return NULL;
        Py_INCREF(next);
        if (PySequence_DelItem((PyObject *) self->buf, 0) == -1) {
            Py_DECREF(next);
            return NULL;
        }
    } else {
        next = PyIter_Next(self->iterable);
        if (next == NULL) return NULL;
        Py_INCREF(next);
    }

    return next;
}

static PyObject *
_PushbackIterator_pushback(_PushbackIterator *self, PyObject *args)
{
    PyObject *item;

    if (!PyArg_ParseTuple(args, "O", &item)) return NULL;
    if (PyList_Append((PyObject *) self->buf, item) == -1) return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef _PushbackIterator_methods[] = {
    {"pushback", (PyCFunction)_PushbackIterator_pushback, METH_VARARGS, 
     ""},
    {NULL}  /* Sentinel */
};

PyTypeObject _PushbackIteratorType = {
    PyObject_HEAD_INIT(NULL)
    0,          /*ob_size*/
    "markup._speedups._PushbackIterator", /*tp_name*/
    sizeof(_PushbackIterator),/*tp_basicsize*/
    0,          /*tp_itemsize*/
    (destructor) _PushbackIterator_dealloc, /*tp_dealloc*/
    0,          /*tp_print*/ 
    0,          /*tp_getattr*/
    0,          /*tp_setattr*/
    0,          /*tp_compare*/
    0,          /*tp_repr*/
    0,          /*tp_as_number*/
    0,          /*tp_as_sequence*/
    0,          /*tp_as_mapping*/
    0,          /*tp_hash */

    0,          /*tp_call*/
    0,          /*tp_str*/
    0,          /*tp_getattro*/
    0,          /*tp_setattro*/
    0,          /*tp_as_buffer*/

    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_ITER, /*tp_flags*/
    _PushbackIterator__doc__,/*tp_doc*/

    0,          /*tp_traverse*/
    0,          /*tp_clear*/

    0,          /*tp_richcompare*/
    0,          /*tp_weaklistoffset*/

    (getiterfunc) _PushbackIterator_iter, /*tp_iter*/
    (iternextfunc) _PushbackIterator_next, /*tp_iternext*/

    /* Attribute descriptor and subclassing stuff */

    _PushbackIterator_methods, /*tp_methods*/
    0,          /*tp_members*/
    0,          /*tp_getset*/
    0,          /*tp_base*/
    0,          /*tp_dict*/

    0,          /*tp_descr_get*/
    0,          /*tp_descr_set*/
    0,          /*tp_dictoffset*/

    (initproc) _PushbackIterator_init, /*tp_init*/
    0,          /*tp_alloc  will be set to PyType_GenericAlloc in module init*/
    PyType_GenericNew          /*tp_new*/
};

PyMODINIT_FUNC
init_speedups(void)
{
    PyObject *module;

    if (PyType_Ready(&MarkupType) < 0)
        return;
    if (PyType_Ready(&_ensureType) < 0)
        return;
    if (PyType_Ready(&_PushbackIteratorType) < 0)
        return;

    init_constants();

    module = Py_InitModule("_speedups", NULL);
    Py_INCREF(&MarkupType);
    PyModule_AddObject(module, "Markup", (PyObject *) &MarkupType);
    Py_INCREF(&_ensureType);
    PyModule_AddObject(module, "_ensure", (PyObject *) &_ensureType);
    Py_INCREF(&_PushbackIteratorType);
    PyModule_AddObject(module, "_PushbackIterator",
                       (PyObject *) &_PushbackIteratorType);
}
