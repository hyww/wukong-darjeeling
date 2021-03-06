// vim: ts=2 sw=2
#include <regex.h>
#include <Python.h>

#include "pyzwave-testrtt.h"

#define ADD_NODE_ANY    0x1
#define ADD_NODE_CONTROLLER   0x2
#define ADD_NODE_SLAVE    0x3
#define ADD_NODE_EXISTING  0x4
#define ADD_NODE_STOP    0x5
#define ADD_NODE_STOP_FAILED  0x6
#define ADD_NODE_OPTION_HIGH_POWER  0x80

int initialised = 0;

extern char init_data_buf[256];
extern unsigned int zwave_my_address;


//#define DEBUGF(...)  fprintf(stderr, __VA_ARGS__)
#define DEBUGF(...)


static PyObject* pyzwave_init(PyObject *self, PyObject *args) {
  char *host_or_dev_name;
  regex_t regex;
  int regi;

  regi = regcomp(&regex, "^[[:digit:]]{1,3}\\.[[:digit:]]{1,3}\\.[[:digit:]]{1,3}\\.[[:digit:]]{1,3}$", REG_EXTENDED | REG_NOSUB | REG_ICASE);
  if (regi) { fprintf(stderr, "Could not compile regex\n"); return NULL; }

  if (!PyArg_ParseTuple( args, "s", &host_or_dev_name)) return NULL;

  regi = regexec(&regex, host_or_dev_name, 0, NULL, 0);
  if (!regi) {
    printf("INFO:pyzwave.c init: %s is an IP host\n", host_or_dev_name);
    if (PyZwave_init(host_or_dev_name) < 0) {
      PyErr_SetString(PyExc_IOError, "Call to zwave_init failed.");
      return NULL;
    }
  } else if (regi == REG_NOMATCH) {
    printf("INFO:pyzwave.c init: %s is a non-IP device\n", host_or_dev_name);
    if (PyZwave_init_usb(host_or_dev_name) < 0) {
      PyErr_SetString(PyExc_IOError, "Call to zwave_init failed.");
      return NULL;
    }
  } else {
    printf("INFO:pyzwave.c init: regx match %s failed %d\n", host_or_dev_name, regi);
  }

  regfree(&regex);

  initialised = 1;
  Py_RETURN_NONE;
}

static PyObject* pyzwave_send(PyObject *self, PyObject *args) {
  int dest_address, i, length;
  PyObject *data;
  uint8_t buf[256];

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  if (!PyArg_ParseTuple( args, "iO!", &dest_address, &PyList_Type, &data))
    return NULL;

  length = (int)PyList_Size(data);
  if (length < 0) {
    PyErr_SetString(PyExc_TypeError, "Second argument must be a list of bytes");
    return NULL;
  }
  if (length > 256) {
    PyErr_SetString(PyExc_ValueError, "Payload cannot be longer than 256 bytes");
    return NULL;
  }

  for (i=0; i<length; i++) {
    PyObject *byteAsObject = PyList_GetItem(data, i); /* Can't fail */
    long byteAsLong = PyInt_AsLong(byteAsObject);
    if (byteAsLong > 255 || byteAsLong < 0) {
      PyErr_SetString(PyExc_ValueError, "Data must consist of single bytes");
      return NULL;
    }
    buf[i] = (uint8_t)byteAsLong;
  }

  DEBUGF("INFO:pyzwave.c send: Sending %i bytes to %i: ", length, dest_address);
  for (i=0; i<length; i++) {
    DEBUGF("[%x] ", buf[i]);
  }
  if(PyZwave_send(dest_address, buf, length) == 0) {
    DEBUGF("\nINFO:pyzwave.c send: Done.\n");
    Py_RETURN_NONE;
  } else {
    DEBUGF("INFO:pyzwave.c send: Call to ZW_senddata failed.\n");
    PyErr_SetString(PyExc_IOError, "Call to ZW_senddata failed.");
    return NULL;
  }
}

static PyObject* pyzwave_receive(PyObject *self, PyObject *args) {
  int wait_msec, len;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  if (!PyArg_ParseTuple( args, "i", &wait_msec))
    return NULL;

  len = PyZwave_receive(wait_msec);
  if (len == 0) {
    PyObject* return_value_list = PyList_New(0);
    PyList_Append(return_value_list, Py_None);
    PyList_Append(return_value_list, Py_None);
    return return_value_list;
  } else {
    int i;

    DEBUGF("PYZWAVE: Received %i bytes: ", len);
    for (i=0; i<len; i++)
      DEBUGF("[%x] ", PyZwave_messagebuffer[i]);
    DEBUGF("\n");

    PyObject* message_list = PyList_New(0);
    for (i=0; i<len; i++) {
      PyList_Append(message_list, PyInt_FromLong((long)PyZwave_messagebuffer[i] & 0xFF));
    }
    PyObject* return_value_list = PyList_New(0);
    PyList_Append(return_value_list, PyInt_FromLong((long)PyZwave_src));
    PyList_Append(return_value_list, message_list);
    return return_value_list;
  }
}

static PyObject* pyzwave_add(PyObject *self, PyObject *args) {
  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  if (ZW_AddNodeToNetwork(ADD_NODE_ANY|ADD_NODE_OPTION_HIGH_POWER) < 0) {
    return NULL;
  }

  Py_RETURN_NONE;
}

static PyObject* pyzwave_delete(PyObject *self, PyObject *args) {
  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }
  if (ZW_RemoveNodeFromNetwork(ADD_NODE_ANY|ADD_NODE_OPTION_HIGH_POWER) < 0) {
    return NULL;
  }

  Py_RETURN_NONE;
}

static PyObject* pyzwave_stop(PyObject *self, PyObject *args) {
  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  if (ZW_AddNodeToNetwork(ADD_NODE_STOP) < 0) {
    return NULL;
  }

  Py_RETURN_NONE;
}

static PyObject* pyzwave_poll(PyObject *self, PyObject *args) {

  while (1) {

    fd_set rs;
    struct timeval to;
    char c;
    int n;
    int interval = 500;
    int zwavefd = PyZwave_zwavefd();

    to.tv_sec = interval/1000;
    to.tv_usec = (interval%1000)*1000;

    FD_ZERO(&rs);
    FD_SET(zwavefd, &rs);
#ifdef _WIN32
    FD_SET(sfd_commu, &rs);
#else //_WIN32
    FD_SET(STDIN_FILENO, &rs);
#endif //_WIN32

    n = select(FD_SETSIZE,&rs,NULL,NULL, &to);
    if (n < 0) {
      printf("INFO:pyzwave.c poll: Z-Wave device file is closed !!!\n");
      return Py_BuildValue("");
    }
    else if (n == 0) {  // timeout
      // printf("INFO:pyzwave.c poll: select timeout\n");
      /*return Py_BuildValue("");*/
      break;
    }

    if (FD_ISSET(zwavefd,&rs)) {
      long len=read(zwavefd,&c,1);
      if (len > 0) {
        zwave_check_state(c);
      }
    }

  }

  char ret[1024];
  strcpy(ret, PyZwave_status());
  PyZwave_clearstatus();
  return PyString_FromString(ret);
}

static PyObject* pyzwave_discover(PyObject *self, PyObject *args) {
  int i;
  PyObject* message_list;
  if (!initialised) {
      PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
      return NULL;
    }
  PyZwave_discover();
  message_list = PyList_New(0);
  PyList_Append(message_list, PyInt_FromLong((long)zwave_my_address & 0xFF));
    for (i=0; i<init_data_buf[0]+1; i++) {
      PyList_Append(message_list, PyInt_FromLong((long)init_data_buf[i] & 0xFF));
    }
    return message_list;
}

static PyObject* pyzwave_routing(PyObject *self, PyObject *args) {
  int i;
  int node_id;
  PyObject* neighbor_list;

  if (!PyArg_ParseTuple( args, "i", &node_id))
    return NULL;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  PyZwave_routing((unsigned)node_id);

  neighbor_list = PyList_New(0);
  for (i=1; i<init_data_buf[0]+1; i++) {
    PyList_Append(neighbor_list, PyInt_FromLong((long)init_data_buf[i] & 0xFF));
  }
  return neighbor_list;
}

static PyObject* pyzwave_getDeviceType(PyObject *self, PyObject *args) {
  int node_id;
  PyObject* device_type;

  if (!PyArg_ParseTuple( args, "i", &node_id))
    return NULL;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  PyZwave_get_device_type((unsigned)node_id);

  device_type = PyList_New(0);
  PyList_Append(device_type, PyInt_FromLong((long)pyzwave_basic));
  PyList_Append(device_type, PyInt_FromLong((long)pyzwave_generic));
  PyList_Append(device_type, PyInt_FromLong((long)pyzwave_specific));
  return device_type;
}

static PyObject* pyzwave_getAddr(PyObject *self, PyObject *args) {
  int i;
  PyObject* message_list;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }
  unsigned long network_id = PyZwave_get_addr();
  message_list = PyList_New(0);
  for (i = 0; i < 4; i++){
    PyList_Append(message_list, PyInt_FromLong((long)network_id & 0xFF));
    network_id >>= 8;
  }
  PyList_Append(message_list, PyInt_FromLong((long)zwave_my_address & 0xFF));
  return message_list;
}

static PyObject* pyzwave_hardReset(PyObject *self, PyObject *args) {
  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  if (PyZwave_hard_reset() < 0) {
    return NULL;
  }
  Py_RETURN_NONE;
}

static PyObject* pyzwave_isNodeFail(PyObject *self, PyObject *args) {
  int node_id;

  if (!PyArg_ParseTuple( args, "i", &node_id))
    return NULL;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }

  // method 1:
  //do_test(node_id, 10, 10);
  //return PyInt_FromLong((long)main_ret);

  return PyInt_FromLong((long)PyZwave_is_node_fail(node_id));
}

static PyObject* pyzwave_removeFail(PyObject *self, PyObject *args) {
  int node_id;

  if (!PyArg_ParseTuple( args, "i", &node_id))
    return NULL;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }
  PyZwave_is_node_fail(node_id);
  PyZwave_remove_fail(node_id);
  Py_RETURN_NONE;
}

static PyObject* pyzwave_setdebug(PyObject *self, PyObject *args) {
  int print_debug_info;

  if (!PyArg_ParseTuple( args, "i", &print_debug_info))
    return NULL;
  PyZwave_print_debug_info = print_debug_info;
  Py_RETURN_NONE;
}

static PyObject* pyzwave_setVerbose(PyObject *self, PyObject *args) {
  int vb;

  if (!PyArg_ParseTuple( args, "i", &vb))
    return NULL;
  verbose = vb;
  Py_RETURN_NONE;
}

static PyObject* pyzwave_basicSet(PyObject *self, PyObject *args) {
  int node_id, value;

  if (!initialised) {
    PyErr_SetString(PyExc_IOError, "Call pyzwave.init first.");
    return NULL;
  }
  if (!PyArg_ParseTuple( args, "ii", &node_id, &value))
    return NULL;
  PyZwave_basic_set((unsigned)node_id, (unsigned)value);
  Py_RETURN_NONE;
}

PyMethodDef methods[] = {
  {"init", pyzwave_init, METH_VARARGS, "Sets the address to connect to"},
  {"send", pyzwave_send, METH_VARARGS, "Sends a list of bytes to a node"},
  {"receive", pyzwave_receive, METH_VARARGS, "Receive data"},
  {"add", pyzwave_add, METH_VARARGS, "Goes into add mode"},
  {"delete", pyzwave_delete, METH_VARARGS, "Goes into delete mode"},
  {"stop", pyzwave_stop, METH_VARARGS, "Stop adding/deleting nodes"},
  {"poll", pyzwave_poll, METH_VARARGS, "Polling current status"},
  {"discover", pyzwave_discover, METH_VARARGS, "Gets discover nodes"},
  {"routing", pyzwave_routing, METH_VARARGS, "Gets node neighbors"},
  {"getDeviceType", pyzwave_getDeviceType, METH_VARARGS, "Gets the device type of a node"},
  {"getAddr", pyzwave_getAddr, METH_VARARGS, "Get Z-Wave address (network ID 4 bytes + node ID 1 byte)"},
  {"hardReset", pyzwave_hardReset, METH_VARARGS, "Hard reset"},
  {"isNodeFail", pyzwave_isNodeFail, METH_VARARGS, "Check if the node fails or not"},
  {"removeFail", pyzwave_removeFail, METH_VARARGS, "Removes a failed node"},
  {"setdebug", pyzwave_setdebug, METH_VARARGS, "Turn debug info on or off"},
  {"setVerbose", pyzwave_setVerbose, METH_VARARGS, "Turn verbose on or off"},
  {"basicSet", pyzwave_basicSet, METH_VARARGS, "Sets a value to a node"},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initpyzwave(void) {
    (void) Py_InitModule("pyzwave", methods);
}
