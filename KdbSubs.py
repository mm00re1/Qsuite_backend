from qpython.qconnection import QConnection
import threading
from qpython.qtype import QException
from qpython.qcollection import QTable
from queue import Queue
import numpy as np
from custom_config_load import *

config = load_config()
custom_ca = config['security']['custom_ca_path']

def wrapQcode(code):
    qFunction = '{[] ' + ''.join(code) + '}'  # Join the lines of code into a single line inside a function
    #block from parsing result greater than 1MB in size, users can view head of result if necessary ie 10#table
    return "{[] response: " + qFunction + "[]; $[1000000 < -22!response; \"can't return preview of objects this large\"; response]}"

def sendFreeFormQuery(kdbFunction, host, port, tls, *args):
    q = QConnection(host=host, port=port, tls_enabled=tls, timeout = 10, custom_ca = custom_ca)
    try:
        q.open()
        response = q.sendSync(kdbFunction, *args)
        #if res is a boolean
        if type(response) is np.bool_:
            if response:
                res = {"success": True, "data": "", "message": "Test Ran Successfully"}
            else:
                res = {"success": False, "data": "", "message": "Test Failed"}
        else:
            string_response = str(response)
            if len(string_response) > 400:
                string_response = string_response[:400] + "......"
            res = {"success": False, "data": string_response, "message": "Response Preview"}

    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e)}
    q.close() 
    return res

def sendFunctionalQuery(kdbFunction, host, port, tls):
    q = QConnection(host=host, port=port, tls_enabled=tls, timeout = 10, custom_ca = custom_ca)
    q.open()
    try:
        response = q.sendSync('.qsuite.executeFunction', kdbFunction)
        #if res is a boolean
        if type(response) is np.bool_:
            if response:
                res = {"success": True, "data": "", "message": "Test Ran Successfully"}
            else:
                res = {"success": False, "data": "", "message": "Test Failed"}
        else:
            string_response = str(response)
            if len(string_response) > 400:
                string_response = string_response[:400] + "......"
            res = {"success": False, "data": string_response, "message": "Response was not Boolean"}

    except Exception as e:
        res = {"success":False, "data": "", "message": "Kdb Error => " + str(e)}
    q.close() 
    return res

def sendKdbQuery(kdbFunction, host, port, tls, *args):
    q = QConnection(host=host, port=port, tls_enabled=tls, timeout = 10, custom_ca = custom_ca)
    q.open()
    res = q.sendSync(kdbFunction, *args)
    q.close()
    return res

def test_kdb_conn(host, port, tls):
    q = QConnection(host=host, port=port, tls_enabled=tls, timeout = 5, custom_ca = custom_ca)
    q.open()
    q.close()
    #throws exception if it times out or port doesn't exist
    return "success"

class kdbSub(threading.Thread):
    def __init__(self, tbl, index, kdb_host, kdb_port):
        super(kdbSub, self).__init__()
        self.q = QConnection(host=kdb_host, port=kdb_port, custom_ca = custom_ca)
        self.q.open()
        self.q.sendSync('.u.sub', numpy.string_(tbl), numpy.string_(index))
        self.message_queue = Queue()
        self._stopper = threading.Event()

    def stopit(self):
        print("unsubbing")
        print("closing conn")
        self.q.close()
        ###self.q.sendAsync(".u.unsub","direct unsub")  --> unsub logic is also handled in .z.pc
        self._stopper.set()

    def stopped(self):
        return self._stopper.is_set()

    def run(self):
        while not self.stopped():
            try:
                message = self.q.receive(data_only = False, raw = False) # retrieve entire message
                if isinstance(message.data, list):
                    # unpack upd message
                    if len(message.data) == 3 and message.data[0] == b'upd' and isinstance(message.data[2], QTable):
                        for row in message.data[2]:
                            self.message_queue.put(row)

            except QException as e:
                print("****Error reading q message, error***: " + str(e))


##utility functions##
def parseKdbTableWithSymbols(table):
    bstr_cols = table.select_dtypes([object]).columns
    for i in bstr_cols:
        table[i] = table[i].apply(lambda x: x.decode('latin'))

def parseKdbListWithSymbols(data):
    return [x.decode('latin') for x in data]
